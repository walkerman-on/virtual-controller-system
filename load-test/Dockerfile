FROM python:3.11-slim

WORKDIR /app

COPY load-test/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY load-test/opcua_controller_emulator.py /app/opcua_controller_emulator.py

CMD ["python", "/app/opcua_controller_emulator.py"]
