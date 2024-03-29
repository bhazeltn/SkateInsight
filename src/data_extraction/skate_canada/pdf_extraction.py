"""
PDF Parsing Script for Skate Canada CSS Documents
Purpose: Extracts specific data from Skate Canada competition PDFs, focusing on Start Order and Results.
Targets: Start Order, Results PDFs generated by CSS software.
Prerequisites: Assumes PDFs follow a consistent format with clear text-based content for extraction.
Author: Bradley Hazelton
Created on: February 02, 2024
Last Updated: February 07, 2024
"""

import pdfplumber
import re
import camelot
import pandas as pd
from pathlib import Path


# Create path to test importing start order
# pdf_path = Path("D:/SkateInsight/data/start_order/23SS1STAR6WomenGFP2SO.pdf")
pdf_path = Path("D:/SkateInsight/data/results/23SS1STAR6WomenGCR.pdf")
# pdf_path = Path("D:/SkateInsight/data/results/2024SECJuniorWomenCR.pdf")
# pdf_path = Path("D:/SkateInsight/data/results/2024SECNoviceWomenCR.pdf")
# pdf_path = Path("D:/SkateInsight/data/results/2024SECNoviceDanceCR.pdf")
# pdf_path = Path("D:/SkateInsight/data/official/23SS1STAR6WomenGFP2OFF.pdf")
# pdf_path = Path(
#    "D:/SkateInsight/data/detail_sheets/23SS1STAR6WomenGFP2DRO.pdf")

date_patterns = [
    # Pattern for written month with optional dash and numeric range
    re.compile(
        r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s\d{1,2}-?\s?(?:to|-)?\s?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)?\s?\d{1,2},?\s\d{4}'),
    # Pattern for purely numeric date ranges
    re.compile(
        r'\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\s?(?:to|-)\s?\d{1,2}[-/]\d{1,2}[-/]\d{4}\b')
]


def find_competition_date_line(text):
    lines = text.strip().split('\n')
    # Limit search to the top 10 lines for the competition date
    search_lines = lines[:10]

    for line in search_lines:
        for pattern in date_patterns:
            if pattern.search(line):
                return line  # Return the matching line as the identified date line

    # If no date line is found in the top 10 lines, return None
    return None


def extract_all_text(pdf_path):
    """
    Extracts all text from a PDF file.

    Parameters:
    - pdf_path (Path): The path to the PDF file.

    Returns:
    - str: A string containing all extracted text from the PDF.
    """
    all_text = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:  # Ensure the page contains text
                all_text += page_text + "\n"

    return all_text


def infer_document_type(text):
    # Simple keyword-based inference for document type
    if "Officials List" in text:
        return "Officials List"
    elif "Starting Order" in text:
        return "Starting Order"
    elif "Category Result Summary" in text:
        return "Category Result Summary"
    # Assuming detail sheets contain unique markers like "Element Score", "Deductions", etc.
    elif "Element Score" in text or "Deductions" in text:
        return "Detail Sheets"
    else:
        return "Unknown"


def extract_detail_sheets_header_info(lines, document_type):
    # Extract header info specific to Detail Sheets
    # Adapt based on Detail Sheets' unique structure
    return {
        "Competition Name": lines[0].strip(),
        "Location": lines[2].strip(),
        "Date Range": lines[1].strip(),
        "Event": lines[3].strip(),
        "Document Type": document_type
    }


def extract_event_sheets_header_info(lines, document_type, date_line_index):
    return {
        "Competition Name": " ".join(lines[:date_line_index - 1]).strip(),
        "Location": lines[date_line_index - 1].strip(),
        "Date Range": lines[date_line_index].strip(),
        "Event": lines[date_line_index + 1].strip(),
        "Document Type": document_type
    }


def extract_header_info(text):
    document_type = infer_document_type(text)
    lines = text.strip().split('\n')
    date_line = find_competition_date_line(text)
    date_line_index = lines.index(date_line) if date_line in lines else -1

    if document_type == "Unknown" or date_line_index == -1:
        return {}

    if document_type in ["Officials List", "Starting Order", "Result Summary"]:
        return extract_event_sheets_header_info(lines, document_type, date_line_index)
    elif document_type == "Detail Sheets":
        return extract_detail_sheets_header_info(lines, document_type)


def extract_tables(pdf_path):
    # This is to be used with Start Orders, Results, and Officials Lists. NOT for Detail Sheets.
    tables = camelot.read_pdf(str(pdf_path), pages='all', flavor="stream")
    # Further process tables if necessary
    if len(tables) > 0:
        # Convert the first table to a DataFrame
        df = tables[0].df

    # Now, df is a Pandas DataFrame containing the extracted table.
    return df


def clean_results_table(extracted_df):
    """
    Cleans the results table DataFrame by dynamically setting headers and filtering rows.

    Parameters:
    - extracted_df: The DataFrame extracted from the PDF containing the results table.

    Returns:
    - A cleaned DataFrame with correct headers and filtered valid rows.
    """
    # Dynamically set headers based on the 'Rank' keyword and clean the DataFrame
    df = set_table_header(extracted_df, 'Rank')

    # Remove the footer information leaving only the ranking table
    df = df[df['Rank'].apply(is_valid_rank)]

    # df = remove_parentheses_from_rankings(df)

    return df


def is_valid_rank(rank):
    if rank.isdigit() or rank == 'WD':  # Check if rank is all digits or 'WD'
        return True
    try:
        # Additional check for numeric ranks that could be floats (in case of decimal ranks, though unlikely)
        float(rank)
        return True
    except ValueError:
        return False


def set_table_header(df, header_keyword):
    """
    Dynamically sets DataFrame headers based on a specific keyword in the rows.

    Parameters:
    - df: The DataFrame to process.
    - header_keyword: The keyword to search for in the DataFrame to identify the header row.

    Returns:
    - A cleaned DataFrame with the correct headers set and unnecessary rows removed.
    """

    header_row_index = None
    for i, row in df.iterrows():
        if row.astype(str).str.contains(header_keyword).any():
            header_row_index = i
            break

    if header_row_index is not None:
        # Set the DataFrame headers to the identified header row
        df.columns = df.iloc[header_row_index]
        # Drop all rows up to and including the header row
        df = df.drop(index=range(header_row_index + 1))

        # After setting headers, you might want to reset the index
        df.reset_index(drop=True, inplace=True)

    return df


def remove_parentheses_from_rankings(df):
    """
    Removes parentheses from ranking columns in the DataFrame and converts to numeric format.

    Parameters:
    - df: DataFrame containing the competition results with ranking columns in parentheses.

    Returns:
    - DataFrame with updated rankings without parentheses.
    """
    for col in df.columns:
        print(type(df[col]))
        # Ensure we are operating on a Series (column) and then check if any value matches the pattern
        if df[col].dtype == 'object' and df[col].str.contains("^\(\d+\)$", regex=True).any():
            # Remove parentheses and convert to float
            df[col] = df[col].str.extract("\((\d+)\)")[0].astype(float)
    return df


print((extract_all_text(pdf_path)))
print(extract_header_info(extract_all_text(pdf_path)))
results_df = (clean_results_table(extract_tables(pdf_path)))

print(results_df)
print(results_df.shape)
print(results_df.head())  # Shows the first few rows of the DataFrame
print(results_df.dtypes)
