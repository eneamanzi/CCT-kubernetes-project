@FOR /f "tokens=*" %i IN ('minikube -p minikube docker-env --shell cmd') DO @%i
 REM non so perchè ma non va se lo eseguo da bat, dewvo lanciarli copiandoli inun cmd
docker build -t producer:latest ./Producer
docker build -t consumer:latest ./Consumer

