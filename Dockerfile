FROM python:3.10-slim-buster 

COPY . /app
WORKDIR /app

RUN python -m pip install --upgrade pip 
RUN python -m pip install -r requirements.txt
EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "knowledge_graph_visualizer.py", "--server.port=8501", "--server.address=0.0.0.0"]