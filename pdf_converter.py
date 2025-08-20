import streamlit as st
import tabula
import pandas as pd
import uuid
from io import BytesIO, StringIO
import os
import pdfplumber
from PIL import Image
import pytesseract
import base64

# Page config
st.set_page_config(page_title="Multi-Level Header PDF Extractor", page_icon="📊", layout="wide")

# Custom CSS for modern and clean UI, preserving original markdown style
st.markdown("""
    <style>
    .stApp { 
        background-color: #f9fafb; 
        font-family: 'Arial', sans-serif;
    }
    .big-font { 
        font-size: 30px !important; 
        font-weight: bold; 
        color: #4a90e2; 
        text-align: center; 
        margin-bottom: 20px;
    }
    .subtitle {
        text-align: center;
        font-size: 18px;
        color: #4b5563;
        margin-bottom: 30px;
    }
    .csv-download-button {
        display: inline-block;
        padding: 10px 20px;
        background-color: #4a90e2;
        color: white !important;
        text-decoration: none !important;
        border-radius: 8px;
        font-weight: 500;
        text-align: center;
        transition: background-color 0.3s ease;
        width: 100%;
        box-sizing: border-box;
    }
    .csv-download-button:hover {
        background-color: #357abd;
        color: white !important;
    }
    .stButton > button {
        background-color: #4a90e2;
        color: white;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 500;
        transition: background-color 0.3s ease;
        width: 100%;
    }
    .stButton > button:hover {
        background-color: #357abd;
    }
    .stTextInput > div > div > input {
        border-radius: 8px;
        border: 1px solid #d1d5db;
        padding: 10px;
    }
    .stSelectbox > div > div > select {
        border-radius: 8px;
        border: 1px solid #d1d5db;
        padding: 10px;
    }
    .stExpander {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        background-color: #ffffff;
    }
    .footer {
        text-align: center;
        color: #6b7280;
        font-size: 14px;
        margin-top: 40px;
        padding: 20px 0;
        border-top: 1px solid #e5e7eb;
    }
    .stSuccess, .stError, .stWarning {
        border-radius: 8px;
        padding: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Configuration for table headers
TABLE_CONFIG = {
    'expected_columns': 7,
    'year_headers': ['', '2074/75 (2017/18)', '2074/75 (2017/18)', '2075/76 (2018/19)', '2075/76 (2018/19)', '2076/77 (2019/20)', '2076/77 (2019/20)'],
    'sub_headers': ['Crops', 'Area', 'Production', 'Area', 'Production', 'Area', 'Production'],
    'crop_keywords': ['lentil', 'chickpea', 'pigeon', 'black', 'gram']
}

# Helper Functions
def create_multi_level_headers(input_dataframe):
    """Create properly structured multi-level headers matching the PDF format."""
    if len(input_dataframe.columns) == TABLE_CONFIG['expected_columns']:
        multi_columns = pd.MultiIndex.from_tuples(
            list(zip(TABLE_CONFIG['year_headers'], TABLE_CONFIG['sub_headers'])),
            names=['Year', 'Measure']
        )
        data_start_row = 0
        for i in range(min(4, len(input_dataframe))):
            first_cell = str(input_dataframe.iloc[i, 0]).strip().lower()
            if first_cell and any(crop in first_cell for crop in TABLE_CONFIG['crop_keywords']):
                data_start_row = i
                break
            elif first_cell and first_cell not in ['crops', 'nan', 'unnamed', '', 'area', 'production']:
                data_start_row = i
                break
        processed_dataframe = input_dataframe.iloc[data_start_row:].copy()
        processed_dataframe.columns = multi_columns
        processed_dataframe = processed_dataframe.reset_index(drop=True)
        return processed_dataframe, True
    return input_dataframe, False

def show_table_structure(processed_dataframe):
    """Display the column structure and a preview of the first few rows."""
    with st.expander("🔍 Table Structure & Preview"):
        st.markdown("*Column Structure:*")
        if isinstance(processed_dataframe.columns, pd.MultiIndex):
            for j, (year, measure) in enumerate(processed_dataframe.columns):
                if str(year).strip():
                    year_clean = year.split('(')[0].strip()
                    st.write(f"Column {j+1}: *{year_clean}* - {measure}")
                else:
                    st.write(f"Column {j+1}: {measure}")
        else:
            st.write([str(c) for c in processed_dataframe.columns])
        st.markdown("*First 3 Rows Preview:*")
        if len(processed_dataframe) > 0:
            st.dataframe(processed_dataframe.head(3), use_container_width=True)
        else:
            st.warning("⚠ No rows extracted in this table.")

def download_buttons(input_dataframe, table_index, session_id, has_multi_level_headers):
    """Generate CSV and Excel download buttons for a given table."""
    st.markdown("*Download Options:*")
    col_csv, col_excel = st.columns(2)
    with col_csv:
        csv_buffer = StringIO()
        if has_multi_level_headers and isinstance(input_dataframe.columns, pd.MultiIndex):
            for level in range(input_dataframe.columns.nlevels):
                header_row = [str(x) for x in input_dataframe.columns.get_level_values(level)]
                pd.DataFrame([header_row]).to_csv(csv_buffer, index=False, header=False)
            input_dataframe.to_csv(csv_buffer, index=False, header=False)
        else:
            input_dataframe.to_csv(csv_buffer, index=False)
        csv_key = f"csv_data_{table_index}_{session_id}"
        st.session_state[csv_key] = csv_buffer.getvalue()
        csv_data = st.session_state[csv_key]
        b64 = base64.b64encode(csv_data.encode()).decode()
        href = f'<a class="csv-download-button" href="data:text/csv;base64,{b64}" download="table_{table_index + 1}.csv">📄 CSV - Table {table_index + 1}</a>'
        st.markdown(href, unsafe_allow_html=True)
    with col_excel:
        excel_buffer = BytesIO()
        excel_df = input_dataframe.copy()
        if has_multi_level_headers and isinstance(input_dataframe.columns, pd.MultiIndex):
            clean_columns = [' - '.join([str(l) for l in col if l]) for col in input_dataframe.columns]
            excel_df.columns = clean_columns
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            excel_df.to_excel(writer, index=False, sheet_name='Data')
        excel_buffer.seek(0)
        st.download_button(
            label=f"📊 Excel - Table {table_index + 1}",
            data=excel_buffer.getvalue(),
            file_name=f"table_{table_index + 1}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"excel_{table_index}_{session_id}",
            use_container_width=True
        )

def ocr_fallback(pdf_bytes, pages_input):
    """Perform OCR-based table extraction for scanned PDFs."""
    ocr_tables = []
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            page_nums = [int(x) - 1 for x in pages_input.split(",") if x.strip().isdigit()]
            for page_num in page_nums:
                page = pdf.pages[page_num]
                image = page.to_image(resolution=300).original
                text = pytesseract.image_to_string(Image.fromarray(image))
                df = pd.DataFrame([line.split() for line in text.split("\n") if line.strip()])
                ocr_tables.append(df)
    except Exception as e:
        st.error(f"❌ OCR failed: {str(e)}")
    return ocr_tables

@st.cache_data
def read_pdf_tables(file_path, pages, mode):
    """Read tables from a PDF file using tabula with caching."""
    return tabula.read_pdf(file_path, pages=pages, multiple_tables=True, pandas_options={'header': None}, **mode)

def validate_pages_input(pages_input):
    """Validate that pages_input contains valid page numbers."""
    try:
        page_nums = [int(x) for x in pages_input.split(",") if x.strip()]
        return all(p > 0 for p in page_nums)
    except ValueError:
        return False

# Main App Interface
st.markdown('<p class="big-font">📊 Convert PDF to CSV File</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Extract PDF data into CSV Format!</p>', unsafe_allow_html=True)

# Initialize session state
if 'tables' not in st.session_state:
    st.session_state.tables = None
if 'pdf_bytes' not in st.session_state:
    st.session_state.pdf_bytes = None
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]
if 'extraction_attempted' not in st.session_state:
    st.session_state.extraction_attempted = False

# File uploader
uploaded_file = st.file_uploader("Upload your PDF file", type="pdf", help="Select a PDF file with tables")

if uploaded_file:
    pdf_bytes = uploaded_file.read()
    st.session_state.pdf_bytes = pdf_bytes
    st.success(f"✅ Uploaded {uploaded_file.name}")

    # Input fields
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        pages_input = st.text_input("Pages to extract", value="1", help="Enter page numbers (e.g., 1,2,3)")
    with col2:
        extraction_mode = st.selectbox(
            "Extraction Mode",
            ["Lattice (borders/grid)", "Stream (aligned text)"],
            help="Choose based on table structure"
        )
    with col3:
        output_format = st.selectbox(
            "Output Format",
            ["CSV (multi-row headers)", "Excel (multi-level headers)", "Both"],
            help="Select output file format"
        )

    if st.button("🚀 Extract with Perfect Headers", type="primary"):
        st.session_state.extraction_attempted = True
        if not validate_pages_input(pages_input):
            st.error("❌ Please enter valid page numbers (e.g., 1,2,3).")
            st.session_state.extraction_attempted = False
        else:
            try:
                with st.spinner("Extracting tables..."):
                    mode = {
                        "Lattice (borders/grid)": {"lattice": True, "stream": False},
                        "Stream (aligned text)": {"lattice": False, "stream": True}
                    }[extraction_mode]
                    temp_path = f"temp_pdf_{st.session_state.session_id}.pdf"
                    with open(temp_path, "wb") as f:
                        f.write(pdf_bytes)
                    tables = read_pdf_tables(temp_path, pages_input, mode)
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    if not tables or all(t.empty for t in tables):
                        st.warning("⚠ No tables extracted with Tabula. Trying OCR...")
                        tables = ocr_fallback(pdf_bytes, pages_input)
                    st.session_state.tables = tables
                    st.session_state.pdf_bytes = None
            except Exception as e:
                if "Invalid page" in str(e):
                    st.error("❌ Invalid page number. Please check the PDF page range.")
                else:
                    st.error(f"❌ Extraction failed: {str(e)}")
                st.session_state.extraction_attempted = False

    if st.session_state.extraction_attempted and st.session_state.tables:
        if len(st.session_state.tables) > 0:
            st.success(f"✅ Found {len(st.session_state.tables)} table(s)")
            for i, table in enumerate(st.session_state.tables):
                st.markdown(f"### Table {i+1} (Raw Preview)")
                st.write(f"Shape: {table.shape}")
                st.dataframe(table.head(10), use_container_width=True)
                if table.empty or len(table.columns) < 2:
                    st.warning("⚠ Table is empty or too small, skipping processing.")
                    continue
                processed_dataframe, has_multi_level_headers = create_multi_level_headers(table)
                if has_multi_level_headers:
                    st.markdown("*Multi-level headers detected and applied*")
                    show_table_structure(processed_dataframe)
                    st.dataframe(processed_dataframe, use_container_width=True)
                    download_buttons(processed_dataframe, i, st.session_state.session_id, True)
                else:
                    st.markdown("*Standard table structure detected*")
                    st.dataframe(processed_dataframe, use_container_width=True)
                    download_buttons(processed_dataframe, i, st.session_state.session_id, False)

# Help Section
with st.expander("💡 How This Works"):
    st.markdown("""
    - *Extraction Mode*:
        - Lattice: Best for tables with visible borders/gridlines.
        - Stream: Best for tables with aligned text but no borders.
    - Uses Tabula for extraction, with OCR fallback for scanned PDFs.
    - Shows raw table previews and processed tables with multi-level headers.
    - Download as *CSV* (with multi-row headers) or *Excel*.
    """)

# Footer
st.markdown("""
    <div class="footer">
        <p>Developed by dev.fero | Address: Bharatpur-11, Chitwan</p>
        <p>© 2025 FeroCS Solutions. All rights reserved.</p>
    </div>
""", unsafe_allow_html=True)