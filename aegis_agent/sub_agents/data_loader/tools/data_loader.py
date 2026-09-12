import os
import zipfile

def run_data_loader(zip_path: str) -> dict:
    """
    Descomprime el archivo ZIP, detecta los PDFs e infiere el nombre de la norma.
    Retorna un diccionario con la lista de documentos.
    """
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"File not found: {zip_path}")

    # Carpeta destino igual al nombre del zip sin extension
    extract_dir = os.path.splitext(zip_path)[0]
    os.makedirs(extract_dir, exist_ok=True)

    documents = []

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for filename in zip_ref.namelist():
            if filename.lower().endswith(".pdf"):
                pdf_real_path = os.path.join(extract_dir, filename)

                # Intentar extraer solo si no existe, o capturar el error si está bloqueado por otro programa
                if not os.path.exists(pdf_real_path):
                    try:
                        zip_ref.extract(filename, extract_dir)
                    except PermissionError:
                        pass # Si está bloqueado y falla, igual lo intentamos leer

                # Recuperar nombre de archivo base
                basename = os.path.basename(filename)

                # Regla corregida: Reemplazar _ por / según la aclaración
                name_without_ext = os.path.splitext(basename)[0]
                norm_reference_name = name_without_ext.replace("_", "/")

                # Construimos la ruta real
                pdf_real_path = os.path.join(extract_dir, filename)

                documents.append({
                    "pdf_path": pdf_real_path,
                    "norm_reference_name": norm_reference_name,
                    "nombre_archivo_pdf": basename
                })

    return {"documents": documents}
