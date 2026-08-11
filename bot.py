import os
import logging
import tempfile
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from utils.converter import convert_images_to_pdf
import asyncio

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

# Bot state management (simple in-memory storage for sessions)
user_sessions = {}

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when /start is issued."""
    user = update.effective_user
    welcome_message = (
        f"👋 Hello {user.first_name}!\n\n"
        "I'm a bot that converts images to PDF files.\n\n"
        "📸 How to use me:\n"
        "1. Send me one or multiple images\n"
        "2. I'll collect them in a session\n"
        "3. Use /convert to create a PDF\n"
        "4. Use /clear to clear your session\n\n"
        "📝 Commands:\n"
        "/start - Show this message\n"
        "/convert - Convert all images to PDF\n"
        "/clear - Clear your image session\n"
        "/help - Show help message\n\n"
        "Send me images and I'll save them for conversion!"
    )
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message."""
    help_text = (
        "🤖 Help Guide\n\n"
        "1. Send images (JPG, PNG, JPEG, WEBP, BMP, TIFF)\n"
        "2. Use /convert to merge all images into a single PDF\n"
        "3. Use /clear to remove all images from your session\n"
        "4. Each user has their own session\n\n"
        "⚠️ Notes:\n"
        "- Images are processed in the order you send them\n"
        "- Maximum 20 images per session\n"
        "- Images are automatically deleted after conversion\n"
        "- No data is permanently stored\n\n"
        "For any issues, contact @your_support_handle"
    )
    await update.message.reply_text(help_text)

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming images."""
    user_id = str(update.effective_user.id)
    
    # Initialize user session if not exists
    if user_id not in user_sessions:
        user_sessions[user_id] = []
    
    # Check if user has too many images
    if len(user_sessions[user_id]) >= 20:
        await update.message.reply_text(
            "⚠️ You've reached the maximum limit of 20 images. "
            "Use /convert to create a PDF or /clear to start fresh."
        )
        return
    
    # Get the image file
    photo = update.message.photo[-1]  # Get the highest quality version
    file = await photo.get_file()
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        await file.download_to_drive(tmp.name)
        user_sessions[user_id].append(tmp.name)
    
    count = len(user_sessions[user_id])
    await update.message.reply_text(
        f"✅ Image received! ({count}/20)\n"
        f"Send /convert to create PDF or send more images."
    )

async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Convert all images in session to PDF."""
    user_id = str(update.effective_user.id)
    
    if user_id not in user_sessions or not user_sessions[user_id]:
        await update.message.reply_text(
            "❌ No images found in your session.\n"
            "Please send me some images first!"
        )
        return
    
    # Send processing message
    processing_msg = await update.message.reply_text(
        "🔄 Converting your images to PDF... Please wait."
    )
    
    try:
        # Get the list of image paths
        image_paths = user_sessions[user_id]
        
        # Create a temporary PDF file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pdf_tmp:
            pdf_path = pdf_tmp.name
        
        # Convert images to PDF
        await convert_images_to_pdf(image_paths, pdf_path)
        
        # Send the PDF back to user
        with open(pdf_path, 'rb') as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                filename=f"converted_images_{user_id}.pdf",
                caption=f"✅ PDF created successfully!\n\n"
                       f"📄 Pages: {len(image_paths)}\n"
                       f"📁 File size: {os.path.getsize(pdf_path) // 1024} KB"
            )
        
        # Clean up
        for path in image_paths:
            try:
                os.unlink(path)
            except:
                pass
        try:
            os.unlink(pdf_path)
        except:
            pass
        
        # Clear session
        user_sessions[user_id] = []
        
        await processing_msg.edit_text("✅ Conversion complete! PDF sent.")
        
    except Exception as e:
        logger.error(f"Error converting images: {e}")
        await processing_msg.edit_text(
            f"❌ Error converting images: {str(e)}\n"
            "Please try again or use /clear to reset your session."
        )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear user's image session."""
    user_id = str(update.effective_user.id)
    
    if user_id in user_sessions:
        # Delete all temporary files
        for path in user_sessions[user_id]:
            try:
                os.unlink(path)
            except:
                pass
        user_sessions[user_id] = []
    
    await update.message.reply_text(
        "🗑️ Your image session has been cleared.\n"
        "You can now send new images."
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors and notify user."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred. Please try again later."
        )

def main() -> None:
    """Start the bot."""
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("convert", convert_command))
    application.add_handler(CommandHandler("clear", clear_command))
    
    # Add message handler for images
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start bot (using webhook for Railway)
    PORT = int(os.environ.get("PORT", 8443))
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
    
    if WEBHOOK_URL:
        # Running on Railway with webhook
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
        )
    else:
        # Running locally with polling
        logger.info("Starting bot in polling mode...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
