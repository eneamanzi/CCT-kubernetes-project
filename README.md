# Progetto Kubernetes per il corso CCT

Questo repository contiene il progetto per il corso di *Cloud Computing Technologies (CCT)*. L'obiettivo è implementare un'architettura a microservizi su Kubernetes che gestisca eventi tramite un flusso di dati asincrono (Kafka) e un database (MongoDB), il tutto esposto tramite un API Gateway (Kong).

L'architettura include:
* **Kong**: API Gateway per l'esposizione dei servizi.
* **Producer**: Microservizio che riceve dati via API e li pubblica su un topic Kafka.
* **Kafka (Strimzi)**: Message broker per la comunicazione asincrona.
* **Consumer**: Microservizio che consuma eventi da Kafka e li salva su MongoDB.
* **MongoDB**: Database per la persistenza dei dati.
* **Metrics-service**: Microservizio che espone metriche calcolate leggendo da MongoDB.

## Indice
- [Progetto Kubernetes per il corso CCT](#progetto-kubernetes-per-il-corso-cct)
  - [Indice](#indice)
  - [🏗️ Architettura e Flusso dei Dati](#️-architettura-e-flusso-dei-dati)
  - [📋 Prerequisiti](#-prerequisiti)
    - [Necessari](#necessari)
    - [Opzionali](#opzionali)
  - [🚀 Guida all'Installazione](#-guida-allinstallazione)
    - [Setup Iniziale del Cluster](#setup-iniziale-del-cluster)
    - [1. Creazione Namespace](#1-creazione-namespace)
    - [2. Strimzi Kafka Operator](#2-strimzi-kafka-operator)
    - [3. MongoDB](#3-mongodb)
      - [Configurazione Utente Applicativo](#configurazione-utente-applicativo)
    - [4. Kong API Gateway](#4-kong-api-gateway)
    - [5. Microservizi (Producer, Consumer, Metrics)](#5-microservizi-producer-consumer-metrics)
      - [Aggiornamento Microservizi](#aggiornamento-microservizi)
    - [6. Deploy Restante (Secret e Applicazioni)](#6-deploy-restante-secret-e-applicazioni)
    - [6. Deploy Restante (Secret e Applicazioni)](#6-deploy-restante-secret-e-applicazioni-1)
  - [⚙️ Funzionamento](#️-funzionamento)
  - [✨ Caratteristiche (Requisiti Non Funzionali)](#-caratteristiche-requisiti-non-funzionali)
  - [🛠️ Comandi Utili](#️-comandi-utili)
    - [Verificare connessione TLS a Kafka](#verificare-connessione-tls-a-kafka)


---

## 🏗️ Architettura e Flusso dei Dati

Il flusso logico delle richieste è il seguente:

| Step | Componente | Azione |
| :--- | :--- | :--- |
| 1️⃣ | Client HTTP | Chiama `POST /event/...` su Kong |
| 2️⃣ | Producer | Riceve la richiesta da Kong e invia l'evento al topic Kafka `student-events` |
| 3️⃣ | Consumer | Riceve l'evento da Kafka e lo salva in MongoDB |
| 4️⃣ | Metrics-service| Espone un endpoint `GET /metrics` per le metriche calcolate da MongoDB |
| 5️⃣ | Kong | Espone gli ingress per `/event` (Producer) e `/metrics` (Metrics-service) |

---

## 📋 Prerequisiti

### Necessari
* **Docker Engine** (NON Docker Desktop). [Guida installazione Ubuntu](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository)
* **Minikube**
* **kubectl**

### Opzionali
* **Lens**
* **k9s**

---

## 🚀 Guida all'Installazione

Segui questi passaggi per configurare e avviare l'intero stack applicativo.

### Setup Iniziale del Cluster

1.  **(Opzionale) Reset e Pulizia Ambiente:**
    Per ricominciare da capo:
    ```bash
    minikube delete --all
    docker system prune -a -f
    ```
2.  **Avviare Minikube:**
    ```bash
    minikube start
    ```
    *(Se ricevi un errore, aggiungi il tuo utente al gruppo docker)*:
    ```bash
    sudo usermod -aG docker $USER && newgrp docker
    ```

3.  **Impostare l'ambiente Docker:**
    Per utilizzare il Docker daemon interno a Minikube (necessario per buildare le immagini che Kubernetes userà):
    ```bash
    eval $(minikube docker-env)
    ```
    **ATTENZIONE:** Questo comando va eseguito in *ogni terminale* che userai per buildare le immagini Docker.



### 1. Creazione Namespace

Creiamo i namespace per isolare i componenti:
```bash
# Per l'Ingress Controller (Kong)
kubectl create namespace kong

# Per il servizio di metriche
kubectl create namespace metrics

# Per Kafka, Producer, Consumer, e Mongo
kubectl create namespace kafka
```

### 2\. Strimzi Kafka Operator

Installiamo Strimzi per gestire il cluster Kafka.

```bash
helm repo add strimzi https://strimzi.io/charts/
helm repo update
helm install strimzi-cluster-operator strimzi/strimzi-kafka-operator -n kafka
```

✅ *Kafka è configurato (tramite i file YAML in `K8s/`) per usare TLS e autenticazione SCRAM-SHA-512.*

### 3\. MongoDB

Installiamo MongoDB usando Helm.

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install mongo-mongodb bitnami/mongodb --namespace kafka --version 18.1.1
```

*(Se l'installazione fallisce per errori di connessione, riprovare)*

#### Configurazione Utente Applicativo

1.  **Recupera la password di root:**

    ```bash
    kubectl get secret -n kafka mongo-mongodb -o jsonpath='{.data.mongodb-root-password}' | base64 -d
    ```

    *(Annota la password generata, es: `A36NCeYzH4`)*

2.  **Accedi al pod di Mongo:**

    ```bash
    kubectl exec -it -n kafka $(kubectl get pods -n kafka -l app.kubernetes.io/name=mongodb -o jsonpath='{.items[0].metadata.name}') -- bash
    ```

3.  **Avvia la shell Mongo e crea l'utente:**
    Sostituisci `<PASSWORD>` con quella recuperata al punto 1.

    ```bash
    mongosh -u root -p <PASSWORD> --authenticationDatabase admin
    ```

4.  **Nel prompt di Mongo, esegui:**

    ```mongo
    use student_events;

    db.createUser({
      user: "appuser",
      pwd: "appuserpass",
      roles: [ { role: "readWrite", db: "student_events" } ]
    });

    exit;
    ```

Le applicazioni useranno questa stringa di connessione: `mongodb://appuser:appuserpass@mongo-mongodb.kafka.svc.cluster.local:27017/student_events?authSource=student_events`

### 4\. Kong API Gateway

Installiamo Kong e configuriamolo per monitorare i namespace corretti.

```bash
helm repo add kong https://charts.konghq.com
helm repo update
helm install kong kong/kong -n kong
```

Aggiorniamo Kong per fargli "vedere" gli ingress negli altri namespace
```bash
helm upgrade kong kong/kong -n kong \
  --set ingressController.watchNamespaces="{kong,kafka,metrics}"
```

**Verifica installazione Kong:** 

Controlla i servizi interni al cluster nel namespace 'kong':

```bash
kubectl get svc -n kong
```

L'output dovrebbe essere simile a questo (la riga importante è `kong-kong-proxy`):

```text
NAME                           TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)
kong-kong-manager              NodePort       10.109.18.217   <none>        8002:31545/TCP,8445:30670/TCP
kong-kong-metrics              ClusterIP      10.101.88.235   <none>        10255/TCP,10254/TCP
kong-kong-proxy                LoadBalancer   10.105.61.105   <pending>     80:31260/TCP,443:32030/TCP
kong-kong-validation-webhook   ClusterIP      10.110.97.78    <none>        443/TCP
```


Ottieni l'URL pubblico per accedere a Kong dal tuo computer
```bash
minikube service kong-kong-proxy -n kong --url
```


Questo è un comando specifico di Minikube che crea un tunnel di rete dal tuo computer al servizio `kong-kong-proxy` dentro il cluster. L'output stamperà gli URL che puoi usare per inviare richieste all'API Gateway (uno per HTTP e uno per HTTPS):

```text
http://192.168.49.2:31260
http://192.168.49.2:32030
```




### 5\. Microservizi (Producer, Consumer, Metrics)

Dobbiamo buildare le immagini Docker dei nostri microservizi Python.
**Assicurati di aver eseguito `eval $(minikube docker-env)` in questo terminale\!**

```bash
docker build -t producer:latest ./Producer
docker build -t consumer:latest ./Consumer
docker build -t metrics-service:latest ./Metrics-service
```

Per controllare che le immagini siano state create nell'ambiente Minikube:

```bash
docker images
```

#### Aggiornamento Microservizi

Se modifichi il codice (es. `app.py`), devi ricreare l'immagine e riavviare il deployment:

```bash
# Ricrea l'immagine (es. producer)
docker build -t producer:latest ./Producer

# Riavvia il deployment
kubectl rollout restart deployment/producer -n kafka
```

Per riavviare tutti i deployment in un namespace:

```bash
kubectl rollout restart deployment -n kafka
kubectl rollout restart deployment -n metrics
```

### 6\. Deploy Restante (Secret e Applicazioni)


1.  **Crea Secret per Kafka SSL:**
    Questo secret permette ai pod (Producer/Consumer) di comunicare con Kafka tramite TLS.
    **IMPORTANTE:** Questo comando va eseguito *prima* di applicare i manifest K8s.

    ```bash
    kubectl create secret generic kafka-ca-cert -n kafka \
      --from-literal=ca.crt="$(kubectl get secret uni-it-cluster-cluster-ca-cert -n kafka -o jsonpath='{.data.ca\.crt}' | base64 -d)"
    ```

2.  **Deploy di tutti i manifest K8s:**
    Questo comando crea i deployment per Producer, Consumer, Metrics, il Cluster Kafka, gli utenti Kafka e gli Ingress di Kong.

    ```bash
    kubectl apply -f ./K8s
    ```

### 6\. Deploy Restante (Secret e Applicazioni)

L'applicazione dei manifest deve seguire un ordine preciso per permettere a Kafka di generare i secret necessari prima che i microservizi (Producer/Consumer) tentino di utilizzarli.

1.  **Deploy del Cluster Kafka (Cluster + Topic + Utenti):**
    Per prima cosa, applichiamo i manifest che definiscono il Cluster, i Topic e gli Utenti di Kafka. Questo avvierà l'operator Strimzi, che creerà il cluster e genererà il secret `uni-it-cluster-cluster-ca-cert` contenente i certificati CA.

    ```bash
    kubectl apply -f ./K8s/kafka-cluster.yaml
    kubectl apply -f ./K8s/kafka-topic.yaml
    kubectl apply -f ./K8s/kafka-users.yaml
    ```
    **Attendi un minuto** affinché il secret `uni-it-cluster-cluster-ca-cert` venga creato prima di procedere.

2.  **Crea Secret per Kafka SSL (per le App):**
    Ora, creiamo il secret `kafka-ca-cert`. Questo comando legge il certificato CA dal secret generato da Strimzi (`uni-it-cluster-cluster-ca-cert`) e lo salva in un nuovo secret che i nostri pod (Producer e Consumer) useranno per comunicare via TLS con Kafka.

    ```bash
    kubectl create secret generic kafka-ca-cert -n kafka \
      --from-literal=ca.crt="$(kubectl get secret uni-it-cluster-cluster-ca-cert -n kafka -o jsonpath='{.data.ca\.crt}' | base64 -d)"
    ```

3.  **Deploy dei Microservizi e Ingress:**
    Infine, avendo creato il secret `kafka-ca-cert` da cui dipendono, possiamo deployare i manifest restanti dei nostri microservizi (Producer, Consumer, Metrics) e l'Ingress di Kong.

    ```bash
    kubectl apply -f ./K8s
    ```
-----

## ⚙️ Funzionamento

Una volta completato il deploy, il sistema gestisce due flussi principali tramite l'API Gateway Kong:

  * **Richieste POST (`/event`)**

    1.  Le richieste (es. `POST /event/some-data`) vengono inviate a Kong.
    2.  Kong le inoltra al microservizio **Producer**.
    3.  Il Producer valida i dati e li pubblica sulla coda Kafka (`student-events`).
    4.  Il **Consumer** (in ascolto sulla coda) riceve il messaggio.
    5.  Il Consumer salva i dati nel database MongoDB.

  * **Richieste GET (`/metrics`)**

    1.  Le richieste `GET /metrics` arrivano a Kong.
    2.  Kong le inoltra al **Metrics-service**.
    3.  Il Metrics-service interroga MongoDB, calcola le metriche aggregate.
    4.  Il servizio risponde al client (tramite Kong) con le metriche calcolate.

-----

## ✨ Caratteristiche (Requisiti Non Funzionali)

  * **Sicurezza**: La comunicazione tra Producer, Consumer e Kafka è protetta da **TLS**. L'autenticazione a Kafka avviene tramite **SASL SCRAM-SHA-512**.
  * **Fault Tolerance**: Grazie a Kafka, se il Consumer smette di funzionare, i messaggi rimangono nella coda pronti per essere processati non appena il Consumer torna online.
  * **Scalabilità**: È possibile scalare orizzontalmente i pod del Producer per gestire un carico maggiore di richieste in ingresso.
  * **Self-Healing**: Kubernetes riavvia automaticamente i pod (Producer, Consumer, ecc.) in caso di crash.

-----

## 🛠️ Comandi Utili

### Verificare connessione TLS a Kafka

Questo comando esegue un test `openssl` dall'interno di un broker Kafka per verificare che la porta 9093 (bootstrap TLS) sia esposta e funzionante.

```bash
kubectl exec -it uni-it-cluster-broker-0 -n kafka -- \
openssl s_client -connect uni-it-cluster-kafka-bootstrap.kafka.svc.cluster.local:9093 -brief </dev/null
```