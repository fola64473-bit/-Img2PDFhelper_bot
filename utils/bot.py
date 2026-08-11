import os
import sys
import logging
import tempfile
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
import img2pdf
from PIL import Image
import io

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not set!")
    sys.exit(1)

# Bot state management
user_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message."""
    user = update.effective_user
    welcome_message = (
        f"👋 Hello {user.first_name}!\n\n"
        "I convert images to PDF files.\n\n"
        "📸 How to use:\n"
        "1. Send me images\n"
        "2. Use /convert to create PDF\n"
        "3. Use /clear to clear session\n\n"
        "Commands:\n"
        "/start - Show this\n"
        "/convert - Convert to PDF\n"
        "/clear - Clear images\n"
        "/help - Help"
    )
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message."""
    help_text = (
        "🤖 Help Guide\n\n"
        "Send images (JPG, PNG, JPEG, WEBP, BMP)\n"
        "/convert - Merge all images into PDF\n"
        "/clear - Remove all images\n\n"
        "Max 20 images per session"
    )
    await update.message.reply_text(help_text)

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming images."""
    try:
        user_id = str(update.effective_user.id)
        
        # Initialize session
        if user_id not in user_sessions:
            user_sessions[user_id] = []
        
        # Check limit
        if len(user_sessions[user_id]) >= 20:
            await update.message.reply_text(
                "⚠️ Maximum 20 images reached. Use /convert or /clear."
            )
            return
        
        # Get image
        photo = update.message.photo[-1]
        file = await photo.get_file()
        
        # Download to temp file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            user_sessions[user_id].append(tmp.name)
        
        count = len(user_sessions[user_id])
        await update.message.reply_text(
            f"✅ Image {count}/20 received! Send /convert to create PDF."
        )
        
    except Exception as e:
        logger.error(f"Error handling image: {e}")
        await update.message.reply_text("❌ Error processing image. Please try again.")

async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Convert images to PDF."""
    user_id = str(update.effective_user.id)
    
    if user_id not in user_sessions or not user_sessions[user_id]:
        await update.message.reply_text(
            "❌ No images found. Send me some images first!"
        )
        return
    
    processing_msg = await update.message.reply_text(
        "🔄 Converting images to PDF... Please wait."
    )
    
    try:
        image_paths = user_sessions[user_id]
        
        # Create PDF using img2pdf
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pdf_tmp:
            pdf_path = pdf_tmp.name
            
            # Convert using img2pdf
            with open(pdf_path, "wb") as f:
                f.write(img2pdf.convert(image_paths))
        
        # Send PDF
        with open(pdf_path, 'rb') as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                filename=f"converted_images.pdf",
                caption=f"✅ PDF created!\nPages: {len(image_paths)}"
            )
        
        # Cleanup
        for path in image_paths:
            try:
                os.unlink(path)
            except:
                pass
        try:
            os.unlink(pdf_path)
        except:
            pass
        
        user_sessions[user_id] = []
        await processing_msg.edit_text("✅ Conversion complete! PDF sent.")
        
    except Exception as e:
        logger.error(f"Error converting: {e}")
        await processing_msg.edit_text(
            f"❌ Error: {str(e)}\nTry /clear and send images again."
        )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear user's session."""
    user_id = str(update.effective_user.id)
    
    if user_id in user_sessions:
        for path in user_sessions[user_id]:
            try:
                os.unlink(path)
            except:
                pass
        user_sessions[user_id] = []
    
    await update.message.reply_text("🗑️ Session cleared! Send new images.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")

def main() -> None:
    """Start the bot."""
    logger.info("Starting bot...")
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("convert", convert_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_error_handler(error_handler)
    
    # Get port for Railway
    port = int(os.environ.get("PORT", 8443))
    
    # Check if we're on Railway (has WEBHOOK_URL)
    webhook_url = os.environ.get("WEBHOOK_URL")
    
    if webhook_url:
        # Webhook mode (Railway)
        logger.info(f"Starting webhook on port {port}")
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=TOKEN,
            webhook_url=f"{webhook_url}/{TOKEN}"
        )
    else:
        # Polling mode (local development)
        logger.info("Starting polling mode...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
