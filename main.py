import time
import os
import uuid
import json
import boto3
from fastapi import FastAPI, Request, HTTPException
from botocore.exceptions import ClientError
from models import SalesNote
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Sales Service Microservice")
#test f
ENV = os.getenv("APP_ENVIRONMENT", "local")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN") 

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
sns_client = boto3.client('sns', region_name=AWS_REGION)
cloudwatch = boto3.client('cloudwatch', region_name=AWS_REGION)

TABLE_NOTES = dynamodb.Table(os.getenv("TABLE_NOTES", "SalesNotes"))
TABLE_ITEMS = dynamodb.Table(os.getenv("TABLE_ITEMS", "SalesNoteItems"))

def send_metric(name, value, unit='Count'):
    if ENV == 'local':
        print(f" [METRIC - {ENV}] {name}: {value} {unit}")
        return
    try:
        cloudwatch.put_metric_data(
            Namespace='SalesApp/Sales',
            MetricData=[
                {'MetricName': name, 'Dimensions': [{'Name': 'Environment', 'Value': ENV}], 'Value': value, 'Unit': unit},
            ]
        )
    except Exception as e:
        print(f"Error metric: {e}")

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    
    send_metric('ExecutionTime', process_time, 'Milliseconds')
    if 200 <= response.status_code < 300: send_metric('2xx_Responses', 1)
    elif 400 <= response.status_code < 500: send_metric('4xx_Errors', 1)
    elif response.status_code >= 500: send_metric('5xx_Errors', 1)
    return response

@app.get("/")
def health_check():
    return {"status": "ok", "service": "sales-service", "env": ENV}

@app.post("/sales")
def create_sales_note(note: SalesNote):
    note_id = str(uuid.uuid4())
    
    try:
        note_item = {
            'ID': note_id,
            'folio': note.folio,
            'clienteId': note.clienteId,
            'direccionFacturacionId': note.direccionFacturacionId,
            'direccionEnvioId': note.direccionEnvioId,
            'total': str(note.total)
        }
        TABLE_NOTES.put_item(Item=note_item)
        
        for item in note.items:
            item_db = {
                'ID': str(uuid.uuid4()),
                'noteId': note_id,
                'productoId': item.productoId,
                'cantidad': item.cantidad,
                'precioUnitario': str(item.precioUnitario),
                'importe': str(item.importe)
            }
            TABLE_ITEMS.put_item(Item=item_db)
            
        if SNS_TOPIC_ARN:
            sns_message = {'noteId': note_id}
            sns_client.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=json.dumps(sns_message),
                Subject=f"Nueva Venta {note.folio}"
            )
            
        return {"message": "Venta procesada", "noteId": note_id, "status": "pending_pdf"}
        
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))