"""/start, /help, /template — команды, доступные каждому допущенному."""

from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Message

from anki_deck_gen.bot import texts
from anki_deck_gen.bot.commands import set_admin_commands
from anki_deck_gen.bot.pending import PendingStore
from anki_deck_gen.config import BotSettings
from anki_deck_gen.tables.template import build_template_xlsx

router = Router(name="start")


@router.message(CommandStart())
async def start(
    message: Message,
    bot: Bot,
    settings: BotSettings,
    state: FSMContext,
    pending: PendingStore,
    invite_redeemed: bool = False,
) -> None:
    """/start прерывает любой диалог и забывает разобранную Таблицу — чистый лист."""
    await state.clear()
    user = message.from_user
    if user is not None:
        pending.pop(user.id)
        if user.id in settings.admin_ids:
            # Теперь чат с Админом точно существует — меню, которое на старте бота
            # могло не встать («chat not found»), ставится здесь.
            await set_admin_commands(bot, message.chat.id)
    prefix = texts.WELCOME_INVITED if invite_redeemed else ""
    await message.answer(prefix + texts.help_message(settings.example_sheet_url))


@router.message(Command("help"))
async def help_command(message: Message, settings: BotSettings) -> None:
    await message.answer(texts.help_message(settings.example_sheet_url))


@router.message(Command("template"))
async def template(message: Message) -> None:
    """Шаблон генерируется кодом, а не лежит файлом в репозитории: бинарнику в git не место."""
    await message.answer_document(
        BufferedInputFile(build_template_xlsx(), filename=texts.TEMPLATE_FILENAME),
        caption=texts.TEMPLATE_CAPTION,
    )
