import os
import sys
import re
import json
from typing import List, Dict, Tuple, Any

from pdfminer.high_level import extract_text
from google import genai

from logger import logger


class TransactionsParserServicePOC:
    def __init__(self, pdf_path: str, google_ai_api_key: str, pdf_password: str = None):
        self.pdf_path = pdf_path
        self.google_ai_api_key = google_ai_api_key
        self.pdf_password = pdf_password

    def extract_text_pdf(self):
        return extract_text(self.pdf_path, password=self.pdf_password)

    def get_pdf_data_with_ai(self, text: str) -> str:
        ## TODO pasar prompt a Ingles
        prompt = f"""
        El texto de abajo es sacado de un pdf, del estado de cuenta de mi tarjeta de crédito.
        Se obtuvo con Python. Tiene las transacciones del mes: fechas, conceptos, importe.
        ¿Podrías obtener esa información y darme un JSON con las transacciones? 
        Sólo dame como resultado el JSON, sin indicar los "```json" al comienzo y final.
        El texto:
        {text}
        """
        client = genai.Client(api_key=self.google_ai_api_key)

        response = client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt
        )
        logger.info(response.text)
        return response.text

    def text_pdf_to_transactions(self, pdf_text: str) -> List[Dict[str, Any]]:
        """
        Converts the IA response (str) to Python List.
        """
        pdf_data = self.get_pdf_data_with_ai(pdf_text)
        pdf_data = pdf_data.replace("```json", "").replace("```", "")
        return json.loads(pdf_data)

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
        total = 0

        for trans in transactions:
            concept = trans["concepto"]
            if not skip_concept_patters.search(concept):
                str_date: str = trans["fecha"]
                amount: str = trans["importe"]

                if "-" in amount:
                    amount = amount.replace("-", "")
                    amount = "-" + amount

                amount = float(amount.replace(".", "").replace(",", "."))

                data.append({
                    "date": str_date.replace("/", "-"),
                    "amount": amount,
                    "concept": concept,
                })
                total += amount

        return data, total

    def get_transactions(self) -> Tuple[List[Dict[str, Any]], int]:
        pdf_text = self.extract_text_pdf()
        transactions = self.text_pdf_to_transactions(pdf_text)
        transactions, total = self.transform_transactions(transactions)
        return transactions, total


def main():
    file = "pdfs/santander_2025-04.pdf"
    ci_passw_pdf = os.getenv("CI_PASSW_PDF")
    google_ai_api_key = os.getenv("GOOGLE_AI_API_KEY")

    if not ci_passw_pdf or not google_ai_api_key:
        logger.error("Missing env variables: 'CI_PASSW_PDF' and 'GOOGLE_AI_API_KEY'")
        sys.exit(1)

    try:
        tr_parser = TransactionsParserServicePOC(file, google_ai_api_key, ci_passw_pdf)
        transactions, total = tr_parser.get_transactions()
        logger.info(f"Total Amount $: {total}")
        logger.info(f"Total transactions: {len(transactions)}")
    except Exception as error:
        logger.error(error)


if __name__ == "__main__":
    main()
