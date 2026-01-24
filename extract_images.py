"""
PDF 이미지 추출 스크립트
실행 방법: pip install pymupdf && python extract_images.py
"""
import fitz
import os

pdf_path = 'papers/Toss_Report_GPU_Hill_Climbing_Ensemble_KR.pdf'
output_dir = 'papers/images'

os.makedirs(output_dir, exist_ok=True)

doc = fitz.open(pdf_path)
img_count = 0

for page_num in range(len(doc)):
    page = doc[page_num]
    images = page.get_images()

    for img_index, img in enumerate(images):
        xref = img[0]
        base_image = doc.extract_image(xref)
        image_bytes = base_image['image']
        image_ext = base_image['ext']

        img_count += 1
        img_filename = f'figure_{img_count}.{image_ext}'
        img_path = os.path.join(output_dir, img_filename)

        with open(img_path, 'wb') as f:
            f.write(image_bytes)
        print(f'Extracted: {img_filename} (page {page_num + 1})')

print(f'\nTotal images extracted: {img_count}')
print(f'Images saved to: {output_dir}/')
