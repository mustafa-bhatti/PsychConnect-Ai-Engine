pip install pypdf --break-system-packages
python3 -c "
from pypdf import PdfWriter, PdfReader
w = PdfWriter()
for path in ['resources/book_htp.pdf', 'resources/book_htp_1964_supplement.pdf']:
    r = PdfReader(path)
    for page in r.pages:
        w.add_page(page)
with open('resources/book_htp_combined.pdf', 'wb') as f:
    w.write(f)
print('Done')
"
