from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, Filters
import requests

AUTHORIZED_USERS = [1259508485]  # Replace with actual Telegram user IDs of authorized users
USER_STATE = {}  # To store temporary state per user



def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    username = user.username
    first_name = user.first_name

    greeting_name = f"{username}" if username else first_name

    update.message.reply_text(
        f"\n RATE: 890/$ \n\nHello, {greeting_name}! Please enter the cryptocurrency and amount for the trade with /trade [crypto] [amount].\nExample: /trade bitcoin 10"
    )

def trade(update: Update, context: CallbackContext) -> None:
    try:
        crypto, amount = context.args
        filter_value, wallet_address, charge, due = create_charge(crypto, amount)  # Fix here
        
        chat_id = update.message.chat_id
        USER_STATE[chat_id] = {'state': 'awaiting_feedback', 'filter_value': filter_value, 'charge': charge}

        # Inform the user about the trade
        update.message.reply_text(f'Order created for {amount} USD worth of {crypto}. Please send {due} {crypto} to the following address: ')

        # Provide the wallet address and the inline keyboard together
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Check Transaction Status ✅", callback_data=filter_value)]
        ])
        update.message.reply_text(f'{wallet_address}', reply_markup=reply_markup)
        
    except Exception as e:
        update.message.reply_text(str(e))


def create_charge(crypto: str, amount: str) -> tuple:
    url = "https://www.poof.io/api/v2/create_charge"
    payload = {
        "amount": amount,
        "crypto": crypto
    }
    headers = {
        "Authorization": "zLpPbbfd4FAeW0rD-_uK0w",
        "content-type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        filter_value = data.get('uuid', 'Failed to get filter value from response.')
        wallet_address = data.get('address', 'Failed to get wallet address from response.')
        charge = data.get('amount', 'Failed to get charge value from response.')
        due = data.get('charge', 'Failed to get due value from response.')  # Fix here
        return filter_value, wallet_address, charge, due
    else:
        raise Exception('Failed to create charge.')

def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()  # Answer the callback query immediately
    chat_id = query.message.chat_id
    filter_value = query.data
    
    check_status_and_notify(context, chat_id, filter_value)

def check_status_and_notify(context: CallbackContext, chat_id: int, filter_value: str):
     # Endpoint to check the status of a transaction
    url = "https://www.poof.io/api/v1/transaction"
    payload = {"transaction": filter_value}
    headers = {
        "Authorization": "zLpPbbfd4FAeW0rD-_uK0w",
        "content-type": "application/json"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    bot = context.bot
    
    if response.status_code == 200:
        data = response.json()
        # Check for the key 'paid' in the JSON response
        paid_status = data.get('paid', None)
        
        if paid_status == 'yes':
            transaction_value = data.get('amount', 'Unknown amount')
            bot.send_message(chat_id=chat_id, text=f"✅ Transaction Successful! Transacted value: {transaction_value} USD ✅\n\nPlease provide your account details for payment...")
            USER_STATE[chat_id] = {
                'state': 'awaiting_feedback',
                'filter_value': filter_value,
                'charge': transaction_value  # Save the transaction_value to the USER_STATE
    }
        elif paid_status == 'no':
            bot.send_message(chat_id=chat_id, text="❌ Transaction Pending ❌ Your crypto transfer has not yet been received. Wait for 15 - 20 mins before checking again. Please ensure you send your coins to the correct address.")
        elif paid_status == 'processing':
            bot.send_message(chat_id=chat_id, text="❌ Transaction Pending ❌ Your crypto transfer has not yet been received. Wait for 15 - 20 mins before checking again. Please ensure you send your coins to the correct address.")

        else:
            bot.send_message(chat_id=chat_id, text="Failed to check transaction status.")

GROUP_CHAT_ID = -956178102  # Replace this with your actual group chat ID.

def handle_feedback(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    user_data = USER_STATE.get(chat_id)

    if user_data and user_data.get('state') == 'awaiting_feedback':
        feedback = update.message.text

        if len(feedback) <= 120:
            user = update.message.from_user
            username = user.username or user.first_name
            user_id = user.id
            filter_value = user_data.get('filter_value', "N/A")
            charge = user_data.get('charge', "N/A")
            
            formatted_feedback = (
                f"Username/FirstName: @{username}\n"
                f"User ID: {user_id}\n"
                f"Transaction ID: {filter_value}\n"
                f"Amount: {charge}\n\n"
                f"Account details: \n{feedback}"
            )

            # Forward the formatted feedback to the group
            try:
                context.bot.send_message(chat_id=GROUP_CHAT_ID, text=formatted_feedback)
                update.message.reply_text('Thank you. Your payment is processing ✅')
                del USER_STATE[chat_id]  # Moved this inside the try block
            except TelegramError as e:
                update.message.reply_text(f"An error occurred while sending feedback: {str(e)}")
            except Exception as e:
                update.message.reply_text(f"An error occurred: {str(e)}")

        else:
            update.message.reply_text('Your response should be 120 characters or less. Please try again.')
            
def resell(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    if user_id not in AUTHORIZED_USERS:
        update.message.reply_text("You are not authorized to use this command!")
        return
    
    try:
        amount, crypto, address = context.args

        result = send_out_of_poof(float(amount), crypto, address)
        update.message.reply_text(result)
        
    except ValueError:
        update.message.reply_text("Please provide the amount, cryptocurrency, and address in the format: /resell [amount] [crypto] [address].\nExample: /resell 2 solana addy")
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")

def send_out_of_poof(amount: float, crypto: str, address: str) -> str:
    url = "https://www.poof.io/api/v2/payouts"
    payload = {
        "amount": amount,
        "crypto": crypto,
        "address": address
    }
    headers = {
        "Authorization": "zLpPbbfd4FAeW0rD-_uK0w",
        "content-type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        return "Transaction successful! ✅"
    else:
        return f"Transaction failed with response: {response.text}"
            
# Integrate paystack's api for naira payouts
            
def main():
    # Use environment variable or external configuration for the bot token
    updater = Updater("6518039936:AAH1WnlgGrPeXAJSk94lJ2pgI3lv-5hr9UI")

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("resell", resell))
    dp.add_handler(CommandHandler("trade", trade))
    dp.add_handler(CallbackQueryHandler(button))  # Handle the callback from the inline keyboard button
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_feedback))  # Handle the feedback input

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
