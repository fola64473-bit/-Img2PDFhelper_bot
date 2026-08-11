import os
from PIL import Image
import img2pdf
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def convert_images_to_pdf(image_paths, output_pdf_path):
    """
    Convert multiple images to a single PDF file.
    Uses img2pdf for high-quality conversion.
    """
    try:
        # Method 1: Using img2pdf (recommended for high quality)
        with open(output_pdf_path, "wb") as f:
            f.write(img2pdf.convert(image_paths))
        return
    
    except Exception as e:
        # Fallback method: Using PIL (if img2pdf fails)
        print(f"img2pdf failed, falling back to PIL: {e}")
        await convert_images_to_pdf_pil(image_paths, output_pdf_path)

async def convert_images_to_pdf_pil(image_paths, output_pdf_path):
    """
    Fallback converter using PIL.
    """
    def convert_sync():
        images = []
        for path in image_paths:
            img = Image.open(path)
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            images.append(img)
        
        if images:
            # Save first image as PDF with others as appended pages
            images[0].save(
                output_pdf_path,
                "PDF",
                save_all=True,
                append_images=images[1:],
                quality=95,
                dpi=(300, 300)
            )
        return True
    
    # Run in thread pool to not block the event loop
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, convert_sync)
