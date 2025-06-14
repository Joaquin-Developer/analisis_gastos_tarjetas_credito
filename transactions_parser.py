import os
import sys
import re
import json
from typing import List, Dict, Tuple, Any
import tempfile
from abc import ABC, abstractmethod

from PyPDF2 import PdfReader, PdfWriter
from google import genai

from logger import logger
import utils


class TransactionsParser(ABC):
    def __init__(self, bank_name: str, currency: str, month: str):
        self.bank_name = bank_name
        self.currency = currency
        self.month = month

    def save_transactions_in_json(self, transactions, json_path: str):
        bank_name = self.bank_name.upper()
        month = self.month.upper()
        currency = self.currency.upper()

        json_str = json.dumps({
            "month": month,
            "str_month": utils.month_str_to_month_name(self.month),
            "bank": bank_name,
            "currency": currency,
            "transactions_total_amount": sum(tran["amount"] for tran in transactions),
            "transactions": transactions,
        }, indent=2)

        os.makedirs("data", exist_ok=True)

        with open(json_path, "w", encoding="utf-8") as f:
            f.write(json_str)
        logger.info("File saved in: %s", json_path)

    @abstractmethod
    def get_transactions(self, path_file_save_json: str = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        Returns a tuple of transactions (List) and total transactions (int)
        """
        ...


class AITransactionsParserService(TransactionsParser):
    "Implements GeminiAI for parse transactions data"
    def __init__(self, bank_name: str, currency: str, month: str, pdf_path: str, google_ai_api_key: str, pdf_password: str = None):
        self.bank_name = bank_name
        self.currency = currency
        self.month = month
        self.pdf_path = pdf_path
        self.google_ai_api_key = google_ai_api_key
        self.pdf_password = pdf_password

    def decrypt_pdf(self) -> str:
        with open(self.pdf_path, "rb") as pdf_file:
            reader = PdfReader(pdf_file)

            if reader.is_encrypted:
                reader.decrypt(self.pdf_password)
            else:
                logger.info("PDF is not encrypted")
                return self.pdf_path

            temp_pdf_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            temp_pdf_path = temp_pdf_file.name
            temp_pdf_file.close()

            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)

            with open(temp_pdf_path, "wb") as f:
                writer.write(f)

            return temp_pdf_path

    def get_pdf_data_with_ai(self) -> str:
        self.pdf_path = self.decrypt_pdf()

        client = genai.Client(api_key=self.google_ai_api_key)
        uploaded_file = client.files.upload(
            file=self.pdf_path,
        )

        # TODO : migrar prompt a inglés (??)
        prompt = """
        El PDF proporcionado es un estado de cuenta mensual de mi tarjeta de crédito enviado por el banco.
        Analiza este documento para extraer la siguiente información de la tabla de movimientos de la tarjeta de crédito:

        Para cada transacción, necesito:
        - "date": La fecha de la transacción en formato "DD/MM/AAAA".
        - "concept": La descripción completa de la operación.
        - "amount": El valor numérico exacto del monto de la transacción, incluyendo su signo (negativo para cargos/débitos, positivo para pagos/créditos).

        **Instrucciones Cruciales para el "amount" (Monto):**
        Asegúrate de que el monto refleje el signo CORRECTO según la naturaleza de la transacción en el estado de cuenta.
        - Si una transacción claramente representa un **gasto o débito** (ej. compras, retiros), el "amount" debe ser **POSITIVO**.
        - Si una transacción claramente representa un **pago o crédito** (ej. pagos a la tarjeta, devoluciones), el "amount" debe ser **NEGATIVO**.
        - Presta atención a las columnas separadas de débitos y créditos si existen, o a cualquier indicación visual de signo.

        **Reglas de Extracción CRÍTICAS:**
        1.  **Manejo ESPECÍFICO de "SEGURO SALDO DEUDOR":**
            * Para la transacción con el concepto "SEGURO SALDO DEUDOR", asegúrate EXPRESAMENTE de que el "amount" sea el **valor numérico directamente asociado a este concepto en la columna de montos del PDF**.
            * Este valor SIEMPRE es un **cargo** y, por lo tanto, debe ser extraído como un **valor positivo** (por ejemplo, "62,52" si es un cargo de esa cantidad) si en el PDF no aparece el signo. **No uses fechas ni otros datos como monto para este concepto.**

        **Formato de Salida:**
        Devuélveme la información ESTRICTAMENTE en formato JSON. El JSON debe contener una lista de objetos de transacción.

        **Esquema del JSON:**
        ```json
        [
            {
                "date": "DD/MM/AAAA",
                "concept": "string",
                "amount": "string"
            }
        ]
        """
        response = client.models.generate_content(
            contents=[
                uploaded_file,
                {"text": prompt}
            ],
            model="gemini-2.0-flash",
            # generation_config=genai.types.GenerationConfig(
            #     response_mime_type="application/json",
            #     temperature=0.0 # Añade esto para reducir la aleatoriedad
            # )
        )
        # logger.info("AI Response:")
        # print(response.text)
        return response.text

    def json_ai_text_to_transactions(self, json_text: str) -> List[Dict[str, Any]]:
        """
        Converts the IA response (str) to Python List.
        """
        json_text = json_text.replace("```json", "").replace("```", "")
        return json.loads(json_text)

    def transform_transactions(self, transactions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        data = []
        keywords_skip = [
            "SALDO ANTERIOR",
            "LEY INCL FINANC",
            "PAGOS",
            "SALDO CONTADO",
            "TOTAL DEV LEY 19210",
        ]
        skip_concept_patters = re.compile("|".join(re.escape(word) for word in keywords_skip))
        total_amount = 0

        for trans in transactions:
            concept = trans["concept"]
            if not skip_concept_patters.search(concept):
                str_date: str = trans["date"]
                amount: str = trans["amount"]

                if amount[-1] == "-":
                    amount = amount.replace("-", "")
                    amount = "-" + amount

                if "," in amount:
                    amount = float(amount.replace(".", "").replace(",", "."))
                else:
                    amount = float(amount)

                data.append({
                    "date": str_date.replace("/", "-"),
                    "amount": amount,
                    "concept": concept,
                })
                total_amount += amount

        return data, total_amount

    def get_transactions(self, path_file_save_json: str = None) -> Tuple[List[Dict[str, Any]], int]:
        ai_response_text = self.get_pdf_data_with_ai()
        json_data = self.json_ai_text_to_transactions(ai_response_text)
        transactions, total = self.transform_transactions(json_data)

        if path_file_save_json:
            self.save_transactions_in_json(transactions, path_file_save_json)

        return transactions, total


class ManualTransactionsParserService(TransactionsParser):
    "Parser for manual uploaded data"
    def __init__(self, bank_name: str, currency: str, month: str, input_path: str):
        self.bank_name: str = bank_name
        self.currency: str = currency
        self.month: str = month
        self.input_path: str = input_path
        # self.transactions: List[Dict[str, Any]] = None

    def load_input_data(self) -> List[str]:
        with open(self.input_path, "r", encoding="utf-8") as file:
            data = file.read()
        return data.split("\n")

    def parse_transactions(self, data: List[str]):
        transactions = []
        total_amount = 0

        for line in data:
            if not line:
                continue
            total_amount += 1

            transaction_data = line.split(" ")
            last_index = len(transaction_data) - 1
            amount = transaction_data[-1]
            if "-" in amount:
                amount = amount.replace("-", "")
                amount = "-" + amount

            amount = float(
                amount.replace(".", "").replace(",", ".")
            )

            transactions.append({
                "date": transaction_data[0],
                "amount": amount,
                "concept": " ".join(transaction_data[2:last_index]),
            })

        return transactions, total_amount

    def get_transactions(self, path_file_save_json: str = None):
        data = self.load_input_data()
        transactions, total = self.parse_transactions(data)

        if path_file_save_json:
            self.save_transactions_in_json(transactions, path_file_save_json)
        return transactions, total


def print_transactions(transactions, total, input_path):
    logs = []
    logs.append(f"File procesado: {input_path}")
    logs.append(f"Total Amount $: {total}")
    logs.append(f"Total transactions: {len(transactions)}\n")

    print("-------------------------------")
    print(*logs, sep="\n")
    print("-------------------------------")
    print(transactions)


def example_ai_parser():
    pdf_password = os.getenv("CI_PASSW_PDF")
    google_ai_api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not pdf_password or not google_ai_api_key:
        logger.error("Missing env variables: 'CI_PASSW_PDF' and 'GOOGLE_AI_API_KEY'")
        sys.exit(1)

    pdf_path = "pdfs/santander_2025-05.pdf"
    bank_name = "Santander"
    currency = "UY$"
    month = "2025-05"

    parser = AITransactionsParserService(bank_name, currency, month, pdf_path, google_ai_api_key, pdf_password)
    transactions, total = parser.get_transactions("data/example_ai.json")

    print_transactions(transactions, total, pdf_path)


def example_manual_parser():
    input_data_path = "input/santander_2025-04_uy$.txt"
    bank_name = "santander"
    month = "2025-04"
    currency = "UY$"

    parser = ManualTransactionsParserService(bank_name, currency, month, input_data_path)
    transactions, total = parser.get_transactions("data/example_manual.json")

    print_transactions(transactions, total, input_data_path)


if __name__ == "__main__":
    print("AI Parser")
    example_ai_parser()
    print("Manual Input Parser")
    example_manual_parser()
