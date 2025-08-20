FROM python:3.10-slim-trixie

ARG SERVICE_PORT=8501
ENV SERVICE_PORT=${SERVICE_PORT}

COPY . /app
WORKDIR /app

RUN python -m pip install --upgrade pip 
RUN python -m pip install -r requirements.txt

RUN apt update && apt install -y ca-certificates curl

# do a dry run to see if the applications would starts (so, we are not surprised if it doesn't work during the real start of the container)
RUN (export DRY_RUN=True; streamlit run kingvisher-knowledge_graph_visualizer.py &) && sleep 5 && curl http://localhost:${SERVICE_PORT}/

HEALTHCHECK CMD curl --fail http://localhost:${SERVICE_PORT}/_stcore/health

ENTRYPOINT streamlit run kingvisher-knowledge_graph_visualizer.py --server.port=${SERVICE_PORT} --server.address=0.0.0.0
