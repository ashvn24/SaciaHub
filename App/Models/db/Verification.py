import csv
from datetime import datetime
import json
import os
import re
from fastapi import HTTPException
import requests


class VerificationLogger:
    def __init__(self, filename="verification_logs.csv"):
        self.filename = filename
        self.initialize_csv()

    def initialize_csv(self):
        """Initialize CSV file with headers if it doesn't exist"""
        headers = [
            'timestamp',
            'verification_type',
            'doc_type',
            'transaction_id',
            'request_data',
            'final_response',
            'status'
        ]

        if not os.path.exists(self.filename):
            with open(self.filename, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(headers)

    def log_verification(self, verification_type, doc_type, transaction_id,
                         request_data, final_response, status):
        """Log verification details with final response"""
        try:
            # Convert request and response data to strings if they're dictionaries
            if isinstance(request_data, dict):
                request_data = json.dumps(request_data)
            if isinstance(final_response, dict):
                final_response = json.dumps(final_response)

            row = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                verification_type,
                doc_type,
                transaction_id,
                request_data,
                final_response,
                status
            ]

            with open(self.filename, 'a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(row)

        except Exception as e:
            print(f"Error logging verification: {str(e)}")


class MOBtoUAN:
    def __init__(self):
        self.logger = VerificationLogger()
        self.initial_request = None
        self.doc_type = None
        self.trans_id = None

    def verify(self, mobile_number, pan_number):
        try:
            print("mob")
            if not mobile_number or not pan_number:
                return False

            self.doc_type = 526
            self.trans_id = "TS1234"
            self.initial_request = {
                "mobile": mobile_number,
                "panNumber": pan_number,
                "docType": self.doc_type,
                "transId": self.trans_id
            }

            url = "https://www.truthscreen.com/v1/apicall/encrypt"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com",
            }

            response = requests.post(
                url, headers=headers, json=self.initial_request)
            if response.status_code == 200:
                return self.encrypt(response.text)
            else:
                self.logger.log_verification(
                    "MOBtoUAN",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at initial encryption: {response.status_code}",
                    "FAILED"
                )
                return False

        except Exception as e:
            self.logger.log_verification(
                "MOBtoUAN",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            return False

    def encrypt(self, encrypted_string):
        try:
            if not encrypted_string:
                return False

            url = "https://www.truthscreen.com/v1/apicall/employment/mobileToUan"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com",
            }
            data = {
                "requestData": encrypted_string
            }

            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                return self.decrypt(response.text)
            else:
                self.logger.log_verification(
                    "MOBtoUAN",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at API call: {response.status_code}",
                    "FAILED"
                )
                return False

        except Exception as e:
            self.logger.log_verification(
                "MOBtoUAN",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            return False

    def decrypt(self, data):
        try:
            if not data:
                return False

            url = "https://www.truthscreen.com/v1/apicall/decrypt"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com",
            }

            response = requests.post(url, headers=headers, data=data)

            # Only log after getting the final decrypted response
            if response.status_code == 200:
                self.logger.log_verification(
                    "MOBtoUAN",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    response.text,
                    "SUCCESS"
                )
                return response.text
            else:
                self.logger.log_verification(
                    "MOBtoUAN",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at decryption: {response.status_code}",
                    "FAILED"
                )
                return False

        except Exception as e:
            self.logger.log_verification(
                "MOBtoUAN",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            return False


class PAN_Verification:
    def __init__(self):
        self.logger = VerificationLogger()
        self.initial_request = None
        self.doc_type = None
        self.trans_id = None
        self.status_code = None

    def verify_pan(self, pan_number):
        try:
            print("pan")
            if not pan_number:
                return False
            if len(pan_number) != 10:
                return False
            if not re.match("[A-Z]{5}[0-9]{4}[A-Z]{1}", pan_number):
                return False

            self.doc_type = 2
            self.trans_id = "206772"
            self.initial_request = {
                "docNumber": pan_number,
                "docType": self.doc_type,
                "transID": self.trans_id
            }

            url = "https://www.truthscreen.com/InstantSearch/encrypted_string"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com",
            }

            response = requests.post(
                url, headers=headers, json=self.initial_request)
            print("response", response)
            self.status_code = response.status_code
            if response.status_code == 200:
                return self.request_encrypt(response.text)
            else:
                self.logger.log_verification(
                    "PAN",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at initial encryption: {response.status_code}",
                    "FAILED"
                )
                raise HTTPException(status_code=400, detail=f"PAN Verification Server Error")

        except Exception as e:
            self.logger.log_verification(
                "PAN",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            raise HTTPException(status_code=400, detail=f"PAN Verification Server Error: {response.status_code}")

    def request_encrypt(self, encrypted_string):
        try:
            if not encrypted_string:
                return False
            url = "https://www.truthscreen.com/api/v2.2/idsearch"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com",
            }
            data = {"requestData": encrypted_string}

            response = requests.post(url, headers=headers, json=data)
            print(response)
            self.status_code = response.status_code
            if response.status_code == 200:
                return self.decrypt_request(response.text)
            else:
                self.logger.log_verification(
                    "PAN",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at API call:{response.status_code}",
                    "FAILED"
                )
                print(f"Error in request_encrypt: Status code {
                      response.status_code}")
                raise HTTPException(status_code=400, detail="PAN Server Error")
        except Exception as e:
            self.logger.log_verification(
                "PAN",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {response.status_code}",
                "ERROR"
            )
            print(f"Error in request_encrypt: {str(e)}")
            raise HTTPException(status_code=400, detail=f"PAN Verification Server Error")

    def decrypt_request(self, data):
        try:
            if not data:
                return False

            url = "https://www.truthscreen.com/InstantSearch/decrypt_encrypted_string"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com",
            }

            response = requests.post(url, headers=headers, data=data)
            self.status_code = response.status_code
            if response.status_code == 200:
                self.logger.log_verification(
                    "PAN",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    response.text,
                    "SUCCESS"
                )
                return response.text
            else:
                self.logger.log_verification(
                    "PAN",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at decryption: {response.status_code}",
                    "FAILED"
                )
                print(
                    f"Error in decrypt_request: Status code {
                        response.status_code}, Response: {response.text}"
                )
                raise HTTPException(status_code=400, detail="PAN Server Error")
        except Exception as e:
            print(f"Error in decrypt_request: {str(e)}")
            raise HTTPException(status_code=400, detail=f"PAN Verification Server Error")


class Aadhar_Verify:
    def __init__(self):
        self.logger = VerificationLogger()
        self.initial_request = None
        self.doc_type = None
        self.trans_id = None
    

    def get_digilocker_link(self):
        try:
            url = "https://www.truthscreen.com/InstantSearch/encrypted_string"
            headers = {
                "Content-Type": "application/json",
                "username": "test@blackrockitsolutions.com",
            }
            request = {
                "trans_id": "121222",
                "doc_type": "472",
                "action": "LINK"
            }
            response = requests.post(url, headers=headers, json=request)
            print("Response:", response.text)
            if response.status_code == 200:
                return self.encrypt(response.text)
            else:
                raise HTTPException(status_code=400, detail=f"Aadhar Verification Server Error")
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Aadhar Verification Server Error")

    def verify(self, ts_trans_id):
        print("aadhar")
        try:
            if not ts_trans_id:
                return False

            self.doc_type = 53
            self.trans_id = "111111"
            self.initial_request = {
                "ts_trans_id": ts_trans_id,
                "doc_type": "472",
                "action": "STATUS"
            }

            url = "https://www.truthscreen.com/InstantSearch/encrypted_string"
            headers = {
                "Content-Type": "application/json",
                "username": "test@blackrockitsolutions.com",
            }

            response = requests.post(
                url, headers=headers, json=self.initial_request)

            if response.status_code == 200:
                return self.encrypt(response.text)
            else:
                self.logger.log_verification(
                    "Aadhar",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at initial encryption: {response.status_code}",
                    "FAILED"
                )
                print(f"Error verifying Aadhar: Status code {
                      response.status_code}")
                return False
        except Exception as e:
            self.logger.log_verification(
                "Aadhar",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            print(f"Error encrypting Aadhar: {str(e)}")
            return False

    def encrypt(self, encrypted_string):
        try:
            if not encrypted_string:
                return False
            # url = "https://www.truthscreen.com/api/v2.2/idsearch"
            url = "https://www.truthscreen.com/api/v1.0/eaadhaardigilocker/"

            headers = {
                "Content-Type": "application/json",
                "username": "test@blackrockitsolutions.com",
            }

            data = {
                "requestData": encrypted_string
            }

            response = requests.post(url, headers=headers, json=data)
            print("Response in Encrypt:", response.text)

            if response:
                print("Response in Decrypt:", self.decrypt(response.text))
                return self.decrypt(response.text)
            else:
                self.logger.log_verification(
                    "Aadhar",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at API call: {response.status_code}",
                    "FAILED"
                )
                print(f"Error in encrypt: Status code {response.status_code}")
                return False
        except Exception as e:
            self.logger.log_verification(
                "Aadhar",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            print(f"Error in encrypt: {str(e)}")
            return False

    def decrypt(self, data):
        try:
            if not data:
                return False
            url = "https://www.truthscreen.com/InstantSearch/decrypt_encrypted_string"
            headers = {
                "Content-Type": "application/json",
                "username": "test@blackrockitsolutions.com"
            }
            print("Data in Decrypt:", data)
            response = requests.post(url, headers=headers, data=data)
            if response:
                # self.logger.log_verification(
                #     "Aadhar",
                #     self.doc_type,
                #     self.trans_id,
                #     self.initial_request,
                #     response.text,
                #     "SUCCESS"
                # )
                return response.text
            else:
                self.logger.log_verification(
                    "Aadhar",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at decryption: {response.status_code}",
                    "FAILED"
                )
                print(f"Error in decrypt: Status code {response.status_code}")
                return False
        except Exception as e:
            self.logger.log_verification(
                "Aadhar",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            print(f"Error in decrypt: {str(e)}")
            return False
        
class  Aadharotp:
    def __init__(self):
        self.logger = VerificationLogger()
        self.initial_request = None
        self.doc_type = None
        self.trans_id = None
    
    def verify(self, aadhar_num):
        print("aadhar")
        try:
            aadhar_num = str(aadhar_num)
            if not aadhar_num:
                return False
            if len(aadhar_num) != 12:
                return False
            self.doc_type = 211
            self.trans_id = "12345"
            self.initial_request = {
                "aadharNo": aadhar_num,
                "docType": self.doc_type,
                "transId": self.trans_id,
            }
            url = "https://www.truthscreen.com/v1/apicall/encrypt"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com",
            }

            response = requests.post(url, headers=headers, json=self.initial_request)

            if response.status_code == 200:
                return self.encrypt(response.text)
            else:
                self.logger.log_verification(
                    "Aadhar",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at initial encryption: {response.status_code}",
                    "FAILED"
                )
                return False
        except Exception as e:
            self.logger.log_verification(
                "Aadhar",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            return False
    
    def encrypt(self, encrypted_string):
        try:
            if not encrypted_string:
                return False
            url = "https://www.truthscreen.com/v1/apicall/nid/aadhar_get_otp"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com",
            }
            data = {
                "requestData": encrypted_string
            }
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                return self.decrypt(response.text)
            else:
                self.logger.log_verification(
                    "Aadhar",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at API call: {response.status_code}",
                    "FAILED"
                )
                return False
        except Exception as e:
            self.logger.log_verification(
                "Aadhar",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            return False
    
    def decrypt(self, data):
        try:
            if not data:
                return False
            url = "https://www.truthscreen.com/v1/apicall/decrypt"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com"
            }
            response = requests.post(url, headers=headers, data=data)

            if response.status_code == 200:
                self.logger.log_verification(
                    "Aadhar",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    response.text,
                    "SUCCESS"
                )
                return response.text
            else:
                self.logger.log_verification(
                    "Aadhar",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at decryption: {response.status_code}",
                    "FAILED"
                )
                return False
        except Exception as e:
            self.logger.log_verification(
                "Aadhar",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            return False
    
    def sendotp(self, otp, data:dict):
        try:
            if not otp and data:
                self.logger.log_verification(
                    "Aadhar",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at otp",
                    "FAILED"
                )
                return False
            url = "https://www.truthscreen.com/v1/apicall/encrypt"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com"
            }
            transId = data.get("transId")
            data = {
            "transId": transId,
            "otp": otp
            }
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                return self.otpsubmit(response.text)
            else:
                self.logger.log_verification(
                    "Aadhar",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at API call: {response.status_code}",
                    "FAILED"
                )
                return False
        except Exception as e:
            self.logger.log_verification(
                "Aadhar",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            return False
    
    def otpsubmit(self, data):
        try:
            if not data:
                return False
            url = "https://www.truthscreen.com/v1/apicall/nid/aadhar_submit_otp"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com"
            }
            response = requests.post(url, headers=headers, data=data)
            if response.status_code == 200:
                return self.decrypt(response.text)
            else:
                self.logger.log_verification(
                    "Aadhar",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at API call: {response.status_code}",
                    "FAILED"
                )
                return False
        except Exception as e:
            self.logger.log_verification(
                "Aadhar",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            return False

class Passport_Verify:
    def __init__(self):
        self.logger = VerificationLogger()
        self.initial_request = None
        self.doc_type = None
        self.trans_id = None

    def verify(self, filenumber, dob):
        print("passport")
        try:
            if not filenumber or not dob:
                return False

            DOB = dob.strftime("%d/%m/%Y")

            self.doc_type = 306
            self.trans_id = "123456"
            self.initial_request = {
                "docNumber": filenumber,
                "docType": self.doc_type,
                "dateOfBirth": DOB,
                "transID": self.trans_id
            }

            url = "https://www.truthscreen.com/InstantSearch/encrypted_string"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com"
            }

            response = requests.post(
                url, headers=headers, json=self.initial_request)
            if response.status_code == 200:
                return self.encrypt(response.text)
            else:
                self.logger.log_verification(
                    "Passport",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at initial encryption: {response.status_code}",
                    "FAILED"
                )
                return False

        except Exception as e:
            self.logger.log_verification(
                "Passport",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            return False

    def encrypt(self, encrypted_string):
        try:
            if not encrypted_string:
                print("No encrypted string to process.")
                return False
            url = "https://www.truthscreen.com/api/v2.2/idsearch"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com"
            }
            data = {
                "requestData": encrypted_string
            }
            response = requests.post(url, headers=headers, json=data)
            print("res", response.text)
            if response.status_code == 200:
                return self.decrypt(response.text)
            else:
                self.logger.log_verification(
                    "Passport",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at API call:{response.status_code}",
                    "FAILED"
                )
                print(f"Error in request_encrypt: Status code {
                      response.status_code}")
                return False
        except Exception as e:
            self.logger.log_verification(
                "Passport",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {response.status_code}",
                "ERROR"
            )
            print(f"Error in encrypt: {str(e)}")
            return False

    def decrypt(self, data):
        try:
            if not data:
                return False
            url = "https://www.truthscreen.com/InstantSearch/decrypt_encrypted_string"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com"
            }

            response = requests.post(url, headers=headers, data=data)
            print("res", response.text)
            if response.status_code == 200:
                self.logger.log_verification(
                    "Passport",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    response.text,
                    "SUCCESS"
                )
                return response.text
            else:
                self.logger.log_verification(
                    "Passport",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at decryption: {response.status_code}",
                    "FAILED"
                )
                return False
        except Exception as e:
            self.logger.log_verification(
                "Passport",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            print(f"Error in decrypt: {str(e)}")
            return False


class UAN_Verification:
    def __init__(self):
        self.logger = VerificationLogger()
        self.initial_request = None
        self.doc_type = None
        self.trans_id = None

    def verify(self, UAN_number):
        print("uan")

        try:
            if not UAN_number:
                return False

            self.doc_type = 337
            self.trans_id = "99998984"
            self.initial_request = {
                "uan": UAN_number,
                "docType": self.doc_type,
                "transID": self.trans_id
            }

            url = "https://www.truthscreen.com/InstantSearch/encrypted_string"

            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com"
            }

            response = requests.post(
                url, headers=headers, json=self.initial_request)

            if response.status_code == 200:
                return self.encrypt(response.text)
            else:
                self.logger.log_verification(
                    "UAN",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at initial encryption: {response.status_code}",
                    "FAILED"
                )
                print(f"Error verifying UAN: Status code {
                      response.status_code}")
                return False
        except Exception as e:
            self.logger.log_verification(
                "UAN",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            print(f"Error encrypting UAN: {str(e)}")
            return False

    def encrypt(self, encrypted_string):
        try:
            if not encrypted_string:
                return False
            url = "https://www.truthscreen.com/api/v2.2/employmentsearch"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com"
            }

            data = {
                "requestData": encrypted_string
            }

            response = requests.post(url, headers=headers, json=data)

            if response.status_code == 200:
                return self.decrypt(response.text)
            else:
                self.logger.log_verification(
                    "UAN",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at API call: {response.status_code}",
                    "FAILED"
                )
                print(f"Error in encrypt: Status code {response.status_code}")
                return False
        except Exception as e:
            self.logger.log_verification(
                "UAN",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            print(f"Error in encrypt: {str(e)}")
            return False

    def decrypt(self, data):
        try:
            if not data:
                return False
            url = "https://www.truthscreen.com/InstantSearch/decrypt_encrypted_string"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com"
            }

            response = requests.post(url, headers=headers, data=data)

            if response.status_code == 200:
                self.logger.log_verification(
                    "UAN",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    response.text,
                    "SUCCESS"
                )
                return response.text
            else:
                self.logger.log_verification(
                    "UAN",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at decryption: {response.status_code}",
                    "FAILED"
                )
                print(f"Error in decrypt: Status code {response.status_code}")
                return False
        except Exception as e:
            self.logger.log_verification(
                "UAN",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            print(f"Error in decrypt: {str(e)}")
            return False


class Criminal_Verification:
    def __init__(self):
        self.logger = VerificationLogger()
        self.initial_request = None
        self.doc_type = None
        self.trans_id = None

    def verify(self, name, address):
        print("criminal")
        try:
            if not name:
                return False

            self.doc_type = 9
            self.trans_id = "123456"
            self.initial_request = {
                "name": name,
                "address": address,
                "docType": self.doc_type,
                "transID": self.trans_id
            }

            url = "https://www.truthscreen.com/InstantSearch/encrypted_string"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com"
            }
            data = {
                "transID": "123456",
                "docType": 9,
                "name": name,
                "address": address
            }

            response = requests.post(
                url, headers=headers, json=self.initial_request)

            if response.status_code == 200:
                return self.encrypt(response.text)
            else:
                self.logger.log_verification(
                    "CourtCheck",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at initial encryption: {response.status_code}",
                    "FAILED"
                )
                return False

        except Exception as e:
            self.logger.log_verification(
                "CourtCheck",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {str(e)}",
                "ERROR"
            )
            return False

    def encrypt(self, encrypted_string):
        try:
            if not encrypted_string:
                return False
            url = "https://www.truthscreen.com/v1/apicall/courtCheck/court_check/check"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com"
            }
            data = {
                "requestData": encrypted_string
            }
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                return self.decrypt(response.text)
            else:
                self.logger.log_verification(
                    "CourtCheck",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at API call:{response.status_code}",
                    "FAILED"
                )
                print(f"Error in request_encrypt: Status code {
                      response.status_code}")
                return False
        except Exception as e:
            self.logger.log_verification(
                "CourtCheck",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {response.status_code}",
                "ERROR"
            )
            print(f"Error in encrypt: {str(e)}")
            return False

    def decrypt(self, data):
        try:
            if not data:
                return False
            url = "https://www.truthscreen.com/InstantSearch/decrypt_encrypted_string"
            headers = {
                "Content-Type": "application/json",
                "username": "production@blackrockitsolutions.com"
            }
            response = requests.post(url, headers=headers, data=data)
            if response.status_code == 200:
                self.logger.log_verification(
                    "CourtCheck",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    response.text,
                    "SUCCESS"
                )
                return response.text
            else:
                self.logger.log_verification(
                    "CourtCheck",
                    self.doc_type,
                    self.trans_id,
                    self.initial_request,
                    f"Failed at decryption: {response.status_code}",
                    "FAILED"
                )
                return False
        except Exception as e:
            self.logger.log_verification(
                "CourtCheck",
                self.doc_type,
                self.trans_id,
                self.initial_request,
                f"Error: {response.status_code}",
                "ERROR"
            )
            print(f"Error in decrypt: {str(e)}")
            return False
