#import docx
#import PyPDF2
#from pptx import Presentation
import pandas as pd
import csv


#read contents form a csv file


def read_csv_file(file_path:str):
    with open(file_path, "r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        text = "\n".join(" | ".join(row) for row in reader)

    return text


#read content from an excel file

def read_excel_file(file_path:str):
    text=[]

    excel_file=pd.read_excel(file_path,sheet_name=None)

    for sheet_name, df in excel_file.items():
        text.append(f"--sheet:{sheet_name}--")

        for index, row in df.iterrows():
            row_parts=[]

            for col in df.columns:
                value = str(row[col]).strip()


                #skip empty cells and invalid pandas placeholder cols
                if value and value!= "nan" and "Unnamed" not in str(col):
                    row_parts.append(f"{col}: {value}")

            if row_parts:
                text.append(" | ".join(row_parts))

    return "\n".join(text)

'''
#read content from a text file

def read_txt_file(file_path:str):
    text=""
    with open(file_path,"r", encoding="utf-8") as file:
        text = file.read()

    return text


#read content from a PDF
def read_pdf_file(file_path:str):
    text=""
    with open(file_path,"rb") as file:
        pdf_reader=PyPDF2.PdfReader(file)
        for page in pdf_reader.pages:
            text += (page.extract_text() or "") + "\n"
    return text


#read content from a Word Document
def read_docx_file(file_path:str):
    doc=docx.Document(file_path)

    text= "\n".join([paragraph.text for paragraph in doc.paragraphs])

    return text

#read content from a pptx, slide by slide!

def read_pptx_file(file_path :str):
    prs=Presentation(file_path)
    text=[]

    #loop through each slide
    for slide_num, slide in enumerate(prs.slides, start=1):
        text.append(f"\n--Slide{slide_num}--")


    #loop thorugh every ppt shape
        for shape in slide.shapes:

            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    if paragraph.text.strip():
                        text.append(paragraph.text.strip())


            if shape.has_table:
                for row in shape.table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            text.append(cell.text.strip())
    return "\n".join(text)


'''
