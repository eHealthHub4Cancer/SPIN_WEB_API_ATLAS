FROM python:3.9-slim

# Install psycopg2 dependencies
RUN pip install psycopg2-binary

# Copy the Python script
COPY scripts/populate.py /scripts/populate.py
COPY scripts/requirements.txt /scripts/requirements.txt

RUN pip install --no-cache-dir -r /scripts/requirements.txt

# Run the script
CMD ["python", "/scripts/populate.py"]