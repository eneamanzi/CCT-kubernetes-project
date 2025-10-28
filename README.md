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
  - [📋 Prerequisiti](#-prerequisiti)
    - [Necessari](#necessari)
    - [Opzionali](#opzionali)
  - [🚀 Guida all'Installazione](#-guida-allinstallazione)
    - [Setup Iniziale del Cluster](#setup-iniziale-del-cluster)
    - [1. Creazione Namespace](#1-creazione-namespace)
    - [2. Strimzi Kafka Operator](#2-strimzi-kafka-operator)
      - [2.1. Deploy del Cluster Kafka:](#21-deploy-del-cluster-kafka)
      - [2.2. Crea Secret per Kafka SSL (per le App):](#22-crea-secret-per-kafka-ssl-per-le-app)
    - [3. MongoDB](#3-mongodb)
      - [3.1. Configurazione Utente Applicativo](#31-configurazione-utente-applicativo)
    - [4. Kong API Gateway](#4-kong-api-gateway)
    - [5. Microservizi (Producer, Consumer, Metrics)](#5-microservizi-producer-consumer-metrics)
      - [5.1. Aggiornamento Microservizi](#51-aggiornamento-microservizi)
    - [6. Deploy Restante](#6-deploy-restante)
  - [🛠️ Comandi di Test (con nip.io)](#️-comandi-di-test-con-nipio)
    - [Inviare Eventi al Producer](#inviare-eventi-al-producer)
      - [Login Utenti:](#login-utenti)
      - [Risultati Quiz:](#risultati-quiz)
      - [Download Materiali:](#download-materiali)
      - [Prenotazione Esami:](#prenotazione-esami)
    - [Leggere le Metriche (Metrics-service)](#leggere-le-metriche-metrics-service)
  - [⚙️ Architettura e Funzionamento (Flusso dei Dati)](#️-architettura-e-funzionamento-flusso-dei-dati)
  - [✨ Proprietà Non Funzionali (TODO)](#-proprietà-non-funzionali-todo)
    - [1. Verificare connessione TLS a Kafka](#1-verificare-connessione-tls-a-kafka)


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

**(Opzionale) Reset e Pulizia Ambiente:**
```bash
minikube delete --all
docker system prune -a -f
```

### Setup Iniziale del Cluster


1.  **Avviare Minikube:**
    ```bash
    minikube start
    ```
    *(Se ricevi un errore, aggiungi il tuo utente al gruppo docker)*:
    ```bash
    sudo usermod -aG docker $USER && newgrp docker
    ```

2.  **Impostare l'ambiente Docker:**
    Per utilizzare il Docker daemon interno a Minikube (necessario per buildare le immagini che Kubernetes userà):
    ```bash
    eval $(minikube docker-env)
    ```
    **ATTENZIONE:** Questo comando va eseguito in *ogni terminale* che userai per buildare le immagini Docker.



### 1. Creazione Namespace

Creiamo i namespace per isolare i componenti:
```bash
kubectl create namespace kong

kubectl create namespace metrics

kubectl create namespace kafka
```

### 2\. Strimzi Kafka Operator

Installiamo Strimzi per gestire il cluster Kafka.

```bash
helm repo add strimzi https://strimzi.io/charts/
helm repo update
helm install strimzi-cluster-operator strimzi/strimzi-kafka-operator -n kafka
```

#### 2.1\. Deploy del Cluster Kafka:

Per prima cosa, applichiamo i manifest che definiscono il Cluster, gli Utenti e i Topic di Kafka. Questo avvierà l'operator Strimzi, che creerà il cluster e genererà il secret `uni-it-cluster-cluster-ca-cert` contenente i certificati CA.

```bash
kubectl apply -f ./K8s/kafka-cluster.yaml
kubectl apply -f ./K8s/kafka-users.yaml
kubectl apply -f ./K8s/kafka-topic.yaml
```
**Attendi un minuto** affinché l'operator crei il cluster. Puoi verificare che il secret `uni-it-cluster-cluster-ca-cert` sia stato creato con successo eseguendo e ottenendo dei secret:

```bash
kubectl get secret uni-it-cluster-cluster-ca-cert -n kafka
```

✅ *Kafka è configurato (tramite i file YAML in `K8s/`) per usare TLS e autenticazione SCRAM-SHA-512.*

#### 2.2\. Crea Secret per Kafka SSL (per le App):

Ora, creiamo il secret `kafka-ca-cert`. Questo comando legge il certificato CA dal secret generato da Strimzi (`uni-it-cluster-cluster-ca-cert`) e lo salva in un nuovo secret che i nostri pod (Producer e Consumer) useranno per comunicare via TLS con Kafka.

```bash
kubectl create secret generic kafka-ca-cert -n kafka \
  --from-literal=ca.crt="$(kubectl get secret uni-it-cluster-cluster-ca-cert -n kafka -o jsonpath='{.data.ca\.crt}' | base64 -d)"
```

### 3\. MongoDB

Installiamo MongoDB usando Helm.

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install mongo-mongodb bitnami/mongodb --namespace kafka --version 18.1.1
```

*(Se l'installazione fallisce per errori di connessione, riprovare)*

#### 3.1\. Configurazione Utente Applicativo

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
    
    1.  Passa al database `student_event`
        ```mongo
        use student_events;
        ```
    2.  Crea l'utenza che verrà usata per accedere al DB
        ```mongo
        db.createUser({
          user: "appuser",
          pwd: "appuserpass",
          roles: [ { role: "readWrite", db: "student_events" } ]
        });
        ```
5.  **Controllare creazione:**

    ```mongo
    use student_events;
    ```

    ```mongo
    db.getUsers()
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

#### 5.1\. Aggiornamento Microservizi

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

### 6\. Deploy Restante

Infine possiamo deployare i manifest restanti
```bash
kubectl apply -f ./K8s
```

## 🛠️ Comandi di Test (con nip.io)

Questi comandi utilizzano il servizio `nip.io` per risolvere i sottodomini (`producer` e `metrics`) direttamente all'IP del tuo cluster Minikube, permettendoti di testare gli Ingress basati su host.

  **Esporta l'IP del Cluster e la Porta del Gateway:**
Esegui questi comandi nel tuo terminale per impostare le variabili d'ambiente.

```bash
IP=$(minikube ip)
# Questo comando estrae solo il numero di porta dall'URL completo
PORT=$(minikube service kong-kong-proxy -n kong --url | head -n 1 | awk -F: '{print $3}')
echo "IP Cluster (IP):    $IP"
echo "Porta Gateway (PORT): $PORT"
```

### Inviare Eventi al Producer
Queste richieste `curl` colpiscono l'host `producer.$IP.nip.io`, che Kong instrada al servizio `producer`.

Per vedere se il consumer riceve effettivamente i dati mandati fare:
```bash
kubectl logs -l app=consumer -n kafka -f
```

#### Login Utenti:

```bash
curl -X POST http://producer.$IP.nip.io:$PORT/event/login -H "Content-Type: application/json" -d '{"user_id": "alice"}'

curl -X POST http://producer.$IP.nip.io:$PORT/event/login -H "Content-Type: application/json" -d '{"user_id": "bob"}'

curl -X POST http://producer.$IP.nip.io:$PORT/event/login -H "Content-Type: application/json" -d '{"user_id": "charlie"}'
```

#### Risultati Quiz:

```bash
curl -X POST http://producer.$IP.nip.io:$PORT/event/quiz -H "Content-Type: application/json" -d '{"user_id": "alice", "quiz_id": "math101", "score": 24, "course_id": "math"}'

curl -X POST http://producer.$IP.nip.io:$PORT/event/quiz -H "Content-Type: application/json" -d '{"user_id": "bob", "quiz_id": "math101", "score": 15, "course_id": "math"}'

curl -X POST http://producer.$IP.nip.io:$PORT/event/quiz -H "Content-Type: application/json" -d '{"user_id": "charlie", "quiz_id": "phys101", "score": 28, "course_id": "physics"}'
```

#### Download Materiali:

```bash
curl -X POST http://producer.$IP.nip.io:$PORT/event/download -H "Content-Type: application/json" -d '{"user_id": "alice", "materiale_id": "pdf1", "course_id": "math"}'

curl -X POST http://producer.$IP.nip.io:$PORT/event/download -H "Content-Type: application/json" -d '{"user_id": "bob", "materiale_id": "pdf1", "course_id": "math"}'

curl -X POST http://producer.$IP.nip.io:$PORT/event/download -H "Content-Type: application/json" -d '{"user_id": "charlie", "materiale_id": "pdf2", "course_id": "physics"}'
```

#### Prenotazione Esami:

```bash
curl -X POST http://producer.$IP.nip.io:$PORT/event/exam -H "Content-Type: application/json" -d '{"user_id": "alice", "esame_id": "math1", "course_id": "math"}'

curl -X POST http://producer.$IP.nip.io:$PORT/event/exam -H "Content-Type: application/json" -d '{"user_id": "bob", "esame_id": "phys1", "course_id": "physics"}'
```

### Leggere le Metriche (Metrics-service)
Queste richieste `curl` colpiscono l'host `metrics.$IP.nip.io`, che Kong instrada al servizio `metrics-service`.

```bash
curl http://metrics.$IP.nip.io:$PORT/metrics/logins
curl http://metrics.$IP.nip.io:$PORT/metrics/quiz/success-rate
curl http://metrics.$IP.nip.io:$PORT/metrics/quiz/average-score
curl http://metrics.$IP.nip.io:$PORT/metrics/downloads
curl http://metrics.$IP.nip.io:$PORT/metrics/exams
```

## ⚙️ Architettura e Funzionamento (Flusso dei Dati)

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


Il flusso logico delle richieste è il seguente:
| Step | Componente | Azione |
| :--- | :--- | :--- |
| 1️⃣ | Client HTTP | Chiama `POST /event/...` su Kong |
| 2️⃣ | Producer | Riceve la richiesta da Kong e invia l'evento al topic Kafka `student-events` |
| 3️⃣ | Consumer | Riceve l'evento da Kafka e lo salva in MongoDB |
| 4️⃣ | Metrics-service| Espone un endpoint `GET /metrics` per le metriche calcolate da MongoDB |
| 5️⃣ | Kong | Espone gli ingress per `/event` (Producer) e `/metrics` (Metrics-service) |



## ✨ Proprietà Non Funzionali (TODO)

  * **Sicurezza**: La comunicazione tra Producer, Consumer e Kafka è protetta da **TLS**. L'autenticazione a Kafka avviene tramite **SASL SCRAM-SHA-512**.
  * **Fault Tolerance**: Grazie a Kafka, se il Consumer smette di funzionare, i messaggi rimangono nella coda pronti per essere processati non appena il Consumer torna online.
  * **Scalabilità**: È possibile scalare orizzontalmente i pod del Producer per gestire un carico maggiore di richieste in ingresso.
  * **Self-Healing**: Kubernetes riavvia automaticamente i pod (Producer, Consumer, ecc.) in caso di crash.

### 1. Verificare connessione TLS a Kafka

Questo comando esegue un test `openssl` dall'interno di un broker Kafka per verificare che la porta 9093 (bootstrap TLS) sia esposta e funzionante.

```bash
kubectl exec -it uni-it-cluster-broker-0 -n kafka -- \
openssl s_client -connect uni-it-cluster-kafka-bootstrap.kafka.svc.cluster.local:9093 -brief </dev/null
```
-----


