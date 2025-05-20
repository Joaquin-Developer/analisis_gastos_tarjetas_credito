import os
import re
import json
from typing import List, Dict, Any

from pdfminer.high_level import extract_text
from google import genai


GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY")


def extract_text_pdf(path: str, password: str = None):
    try:
        return extract_text(path, password=password)
    except FileNotFoundError:
        raise Exception(f"Error: El archivo '{path}' no se encontró.")
    except Exception as error:
        raise Exception(f"Ocurrió un error al leer el PDF con pdfminer.six: {error}")


def get_pdf_data_with_ai(text: str) -> str:
    ## TODO pasar prompt a Ingles
    prompt = f"""
    El texto de abajo es sacado de un pdf, del estado de cuenta de mi tarjeta de crédito.
    Se obtuvo con Python. Tiene las transacciones del mes: fechas, conceptos, importe.
    ¿Podrías obtener esa información y darme un JSON con las transacciones? 
    Sólo dame como resultado el JSON, sin indicar los "```json" al comienzo y final.
    El texto:
    {text}
    """
    client = genai.Client(api_key=GOOGLE_AI_API_KEY)

    response = client.models.generate_content(
        model="gemini-2.0-flash", contents=prompt
    )
    print(response.text)
    return response.text


def transform_transactions(transactions: List[Dict[str, Any]]):
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
                "concept": concept,
                "amount": amount,
            })
            total += amount

    return data, total


def text_pdf_to_transactions(pdf_text: str) -> List[Dict[str, Any]]:
    """
    Converts the IA response (str) to Python List.
    """
    pdf_data = get_pdf_data_with_ai(pdf_text)
    pdf_data = pdf_data.replace("```json", "").replace("```", "")
    json_data = json.loads(pdf_data)
    return json_data


def main():
    file = "pdfs/santander_2025-04.pdf"
    try:
        pdf_text = extract_text_pdf(file, "51243526")
        transactions = text_pdf_to_transactions(pdf_text)
        transactions, total = transform_transactions(transactions)

        for transaction in transactions:
            print(transaction)

        print(f"Total: {total}")
        print(len(transactions))
    except Exception as e:
        print(f"Error en main: {e}")


if __name__ == "__main__":
    main()
