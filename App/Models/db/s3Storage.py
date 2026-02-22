from datetime import datetime
import io
import os
import boto3
from fastapi import HTTPException, UploadFile
import fitz
import httpx
from PIL import Image
from Models.utils.config import settings

class DigitalOceanSpacesManager:
    def __init__(self, bucket_name):
        self.bucket_name = bucket_name
        self.session = boto3.session.Session()
        self.client = self.session.client(
            's3',
            region_name=settings.S3_REGION,
            endpoint_url=settings.S3_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_PRIVATE_KEY
        )

        self.create_folders(['BRITS/User_Docs/', 'BRITS/Company_Docs/'])

    def create_folders(self, folders):
        try:
            folder_responses = []
            for folder_name in folders:
                # Create a folder within the bucket.
                folder_response = self.client.put_object(
                    Bucket=self.bucket_name, Key=folder_name)
                folder_url = f"https://{self.bucket_name}.blr1.digitaloceanspaces.com/{folder_name}"
                folder_responses.append({
                    "FolderName": folder_name,
                    "FolderURL": folder_url,
                    "FolderCreationResponse": folder_response
                })

            # Return the output in a dictionary.
            return {
                "BucketName": self.bucket_name,
                "FoldersCreated": folder_responses
            }

        except Exception as e:
            return {"error": str(e)}

    async def upload_image(self, file: UploadFile, folder_name: str, subfolder_name: str, extract: int):
        try:
            # Generate a unique filename
            file_content = await file.read()
            file_extension = file.filename.split('.')[-1]
            unique_filename = f"{file.filename.split('.')[0]}.{datetime.now()}.{file_extension}"
            subfolder_key = f"{folder_name}{subfolder_name}/"
            file_key = f"{subfolder_key}{unique_filename}"
            content_type = file.content_type
            print(file_extension.lower(), extract)
            if file_extension.lower() == "pdf" and extract==1:
                print("here")
                pdf_doc = fitz.open(stream=file_content, filetype="pdf")
                pix = pdf_doc[0].get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format="PNG")
                img_byte_arr.seek(0)
                file_content = img_byte_arr.getvalue()
                content_type = "image/png"
                unique_filename = unique_filename.replace(".pdf", ".png")
                file_key = file_key.replace(".pdf", ".png")

            # Upload the file
            self.client.put_object(
                Bucket=self.bucket_name, 
                Key=file_key,
                Body=file_content, 
                ContentType=content_type
            )
            # Construct the file URL
            file_url = f"https://{self.bucket_name}.blr1.digitaloceanspaces.com/{file_key}"
            print(unique_filename)
            return unique_filename

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def generate_presigned_url(self, file_key: str, expiration: int = 3600):
        try:
            # response = self.client.get_object(Bucket=self.bucket_name, Key=file_key)
            response = self.client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': file_key,
                    'ResponseContentDisposition': f'inline; filename="{os.path.basename(file_key)}"'
                },
                ExpiresIn=3600, 
            )
            return response
            # content = response['Body'].read()
            # content_type = response.get('ContentType', 'application/octet-stream')
            # base64_content = base64.b64encode(content).decode("utf-8")
            # return Response(
            #     content=base64_content,
            #     media_type=content_type,
            #     headers={
            #         "Access-Control-Allow-Origin": "*",
            #         "Content-Disposition": f"inline; filename={file_key.split('/')[-1]}"
            #     }
            # )

        except httpx.HTTPStatusError as e:
            detail = f"HTTP Status Error: {e.response.status_code} for url {e.request.url}\n{e.response.text}"
            print(detail)
            raise HTTPException(status_code=500, detail=detail)
        except httpx.RequestError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


async def handle_image_in_spaces(action: str, file_name: str = None, file_data: UploadFile = None, folder: str = None, extract: int = None):
    do_spaces_client = DigitalOceanSpacesManager(
        bucket_name='saciahub_clientsdocs')
    print("\n filename:", file_name, "\n filedata:", file_data, "\n folder:", folder)
    if action == 'upload':
        if file_data and file_name:
            result = await do_spaces_client.upload_image(file_data, f'BRITS/{folder}/', file_name, extract)
            return result
        else:
            raise ValueError(
                "For upload action, file_data, file_name, and bucket_name are required.")
    elif action == 'get_url':
        if file_name and folder:
            result = await do_spaces_client.generate_presigned_url(f"BRITS/{folder}/"+file_name)
            return result
        else:
            raise ValueError(
                "For get_url action, file_name, and bucket_name are required.")
    else:
        raise ValueError("Invalid action. Use 'upload' or 'get_url'.")
