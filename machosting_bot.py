"""
MacHosting Bot - Bot de Discord para hosting y creación de bots 24/7
Requiere: pip install discord.py aiohttp python-dotenv
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import aiohttp
import subprocess
import os
import sys
import json
import tempfile
from datetime import datetime

# ─────────────────────────────────────────────
#  CONFIGURACIÓN
# ─────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PREFIX = "!"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Almacena los subprocesos de bots activos: {user_id: {token, proceso, nombre}}
hosted_bots: dict[int, dict] = {}


# ─────────────────────────────────────────────
#  PANEL PRINCIPAL (vista embebida con botones)
# ─────────────────────────────────────────────
class HostingPanel(discord.ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=300)
        self.user = user
        self.token = None
        self.code = None

    # ── 1. Vincular Token ──────────────────────
    @discord.ui.button(label="1. Vincular Token", style=discord.ButtonStyle.primary, emoji="🔗", row=0)
    async def vincular_token(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ No es tu panel.", ephemeral=True)
        await interaction.response.send_modal(TokenModal(self))

    # ── 2. Pegar Código ───────────────────────
    @discord.ui.button(label="📥 Pegar Código Completo", style=discord.ButtonStyle.success, emoji=None, row=0)
    async def pegar_codigo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ No es tu panel.", ephemeral=True)
        await interaction.response.send_modal(CodigoModal(self))

    # ── 3. Editar con IA ──────────────────────
    @discord.ui.button(label="🤖 Editar con IA", style=discord.ButtonStyle.secondary, row=0)
    async def editar_ia(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ No es tu panel.", ephemeral=True)
        await interaction.response.send_modal(IAModal(self))

    # ── 4. Encender Bot ───────────────────────
    @discord.ui.button(label="🟢 Encender Bot", style=discord.ButtonStyle.success, row=1)
    async def encender_bot(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ No es tu panel.", ephemeral=True)

        uid = self.user.id
        if uid in hosted_bots:
            return await interaction.response.send_message("⚠️ Ya tienes un bot activo. Apágalo primero.", ephemeral=True)

        if not self.token:
            return await interaction.response.send_message("❌ Primero vincula un token.", ephemeral=True)
        if not self.code:
            return await interaction.response.send_message("❌ Primero pega el código de tu bot.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        # Inyectar token en el código
        code_final = self.code.replace("YOUR_TOKEN", self.token).replace("TU_TOKEN", self.token)
        # Si el código no tiene bot.run(), lo añadimos
        if "bot.run(" not in code_final and "client.run(" not in code_final:
            code_final += f'\n\nbot.run("{self.token}")\n'

        # Guardar en archivo temporal
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
        tmp.write(code_final)
        tmp.close()

        try:
            proceso = subprocess.Popen(
                [sys.executable, tmp.name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            hosted_bots[uid] = {
                "token": self.token[:20] + "...",
                "proceso": proceso,
                "archivo": tmp.name,
                "inicio": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
            }
            await interaction.followup.send("✅ **Bot encendido exitosamente.** Está corriendo 24/7.", ephemeral=True)
            await actualizar_panel(interaction.message, len(hosted_bots))
        except Exception as e:
            await interaction.followup.send(f"❌ Error al iniciar: `{e}`", ephemeral=True)

    # ── 5. Apagar Bot ─────────────────────────
    @discord.ui.button(label="🔴 Apagar Bot", style=discord.ButtonStyle.danger, row=1)
    async def apagar_bot(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ No es tu panel.", ephemeral=True)

        uid = self.user.id
        if uid not in hosted_bots:
            return await interaction.response.send_message("⚠️ No tienes ningún bot activo.", ephemeral=True)

        info = hosted_bots.pop(uid)
        info["proceso"].terminate()
        try:
            os.unlink(info["archivo"])
        except Exception:
            pass

        await interaction.response.send_message("🔴 Bot apagado correctamente.", ephemeral=True)
        await actualizar_panel(interaction.message, len(hosted_bots))


async def actualizar_panel(message: discord.Message, total: int):
    """Actualiza el embed del panel con el conteo de bots activos."""
    try:
        embed = crear_embed_panel(total)
        await message.edit(embed=embed)
    except Exception:
        pass


def crear_embed_panel(total_activos: int = 0) -> discord.Embed:
    embed = discord.Embed(
        title="🌐 MacHosting — Panel de Control",
        description="Sube tus bots, enciéndelos y mantenlos activos **24/7** completamente gratis.",
        color=0x5865F2
    )
    embed.add_field(
        name="📖 Manual Rápido",
        value=(
            "**1️⃣ Vincular Token** → Pega el token secreto de tu bot.\n"
            "**2️⃣ Pegar Código** → Sube el script `.py` completo.\n"
            "**3️⃣ Editar con IA** *(opcional)* → Describe qué quieres añadir.\n"
            "**4️⃣ Encender Bot** → Tu bot se activa al instante.\n"
            "**5️⃣ Apagar Bot** → Lo desconecta de forma segura."
        ),
        inline=False
    )
    embed.add_field(
        name="⚙️ Formas de Encendido",
        value=(
            "💠 **Carga Directa:** Pega tu código con comandos nativos.\n"
            "💠 **Asistente IA:** Genera o modifica código con lenguaje natural.\n"
            "💠 **Multi-Instancia:** Cada usuario corre su propio bot aislado."
        ),
        inline=False
    )
    embed.add_field(name="🟢 Bots Activos Ahora", value=f"`{total_activos}` activos", inline=False)
    embed.set_footer(text="MacHosting • Desplegado en servidores multiproceso")
    return embed


# ─────────────────────────────────────────────
#  MODALES
# ─────────────────────────────────────────────
class TokenModal(discord.ui.Modal, title="🔗 Vincular Token de Bot"):
    token = discord.ui.TextInput(
        label="Token secreto de tu bot",
        placeholder="Pega aquí el token de Discord Developer Portal",
        style=discord.TextStyle.short,
        required=True
    )

    def __init__(self, panel: HostingPanel):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction: discord.Interaction):
        self.panel.token = self.token.value.strip()
        await interaction.response.send_message(
            "✅ Token vinculado correctamente. Ahora pega tu código.", ephemeral=True
        )


class CodigoModal(discord.ui.Modal, title="📥 Pegar Código del Bot"):
    codigo = discord.ui.TextInput(
        label="Código Python de tu bot (.py)",
        placeholder="import discord\n...",
        style=discord.TextStyle.long,
        required=True,
        max_length=4000
    )

    def __init__(self, panel: HostingPanel):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction: discord.Interaction):
        self.panel.code = self.codigo.value
        await interaction.response.send_message(
            "✅ Código guardado. Pulsa **Encender Bot** para lanzarlo.", ephemeral=True
        )


class IAModal(discord.ui.Modal, title="🤖 Editar Bot con Inteligencia Artificial"):
    instruccion = discord.ui.TextInput(
        label="¿Qué quieres añadir o cambiar?",
        placeholder="Ej: Añade un comando /saludar que responda con un saludo personalizado",
        style=discord.TextStyle.long,
        required=True
    )

    def __init__(self, panel: HostingPanel):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        codigo_base = self.panel.code or "# Bot vacío, crea uno desde cero"
        prompt = (
            f"Eres un experto en discord.py. El usuario tiene este bot:\n\n"
            f"```python\n{codigo_base[:2000]}\n```\n\n"
            f"Instrucción del usuario: {self.instruccion.value}\n\n"
            f"Devuelve SOLO el código Python completo y funcional, sin explicaciones ni markdown."
        )
        nuevo_codigo = await pedir_ia(prompt)
        if nuevo_codigo:
            self.panel.code = nuevo_codigo
            preview = nuevo_codigo[:500] + ("..." if len(nuevo_codigo) > 500 else "")
            await interaction.followup.send(
                f"✅ **IA generó el código.** Vista previa:\n```python\n{preview}\n```\n"
                "Ahora pulsa **Encender Bot**.",
                ephemeral=True
            )
        else:
            await interaction.followup.send("❌ Error al conectar con la IA. Revisa tu GEMINI_API_KEY.", ephemeral=True)


# ─────────────────────────────────────────────
#  LLAMADA A GEMINI (IA)
# ─────────────────────────────────────────────
async def pedir_ia(prompt: str) -> str | None:
    """
    Llama a Gemini 2.0 Flash — GRATIS en aistudio.google.com/app/apikey
    Límite gratuito: 1,500 requests/día y 1 millón de tokens/min.
    Usa gemini-2.0-flash y cae a gemini-1.5-flash si falla.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "TU_GEMINI_KEY":
        return None

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 2048
        }
    }

    modelos = ["gemini-2.0-flash", "gemini-1.5-flash"]
    for modelo in modelos:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{modelo}:generateContent?key={GEMINI_API_KEY}"
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as r:
                    if r.status == 200:
                        data = await r.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            continue  # Intenta con el siguiente modelo

    return None


# ─────────────────────────────────────────────
#  COMANDOS SLASH
# ─────────────────────────────────────────────
@bot.tree.command(name="panel", description="Abre el panel de hosting de MacHosting")
async def panel(interaction: discord.Interaction):
    embed = crear_embed_panel(len(hosted_bots))
    view = HostingPanel(interaction.user)
    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="mis_bots", description="Ve el estado de tu bot activo")
async def mis_bots(interaction: discord.Interaction):
    uid = interaction.user.id
    if uid not in hosted_bots:
        return await interaction.response.send_message("❌ No tienes ningún bot activo.", ephemeral=True)
    info = hosted_bots[uid]
    embed = discord.Embed(title="🤖 Tu Bot Activo", color=0x57F287)
    embed.add_field(name="Token (parcial)", value=f"`{info['token']}`", inline=False)
    embed.add_field(name="Activo desde", value=info["inicio"], inline=False)
    embed.add_field(name="Estado", value="🟢 Corriendo", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="crear_comando", description="Genera código para un comando nuevo con IA")
@app_commands.describe(descripcion="Describe el comando que quieres crear")
async def crear_comando(interaction: discord.Interaction, descripcion: str):
    await interaction.response.defer(ephemeral=True)
    prompt = (
        f"Eres un experto en discord.py. Crea un comando slash para Discord basado en esta descripción:\n"
        f"'{descripcion}'\n\n"
        f"Devuelve SOLO el bloque de código Python funcional con el decorador @bot.tree.command, "
        f"listo para pegar en un bot existente. Sin explicaciones."
    )
    codigo = await pedir_ia(prompt)
    if codigo:
        # Limpiar posible markdown
        codigo = codigo.replace("```python", "").replace("```", "").strip()
        await interaction.followup.send(
            f"✅ **Comando generado:**\n```python\n{codigo[:1800]}\n```",
            ephemeral=True
        )
    else:
        await interaction.followup.send(
            "❌ IA no disponible. Configura `GEMINI_API_KEY` en el bot.",
            ephemeral=True
        )


@bot.tree.command(name="ayuda_hosting", description="Muestra el manual completo de MacHosting")
async def ayuda_hosting(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📚 Manual de MacHosting",
        description="Sistema de alojamiento multiproceso para bots de Discord.",
        color=0x5865F2
    )
    embed.add_field(name="🔗 /panel", value="Abre el panel principal con todos los botones.", inline=False)
    embed.add_field(name="🤖 /crear_comando [descripción]", value="La IA genera el código de un comando nuevo.", inline=False)
    embed.add_field(name="📊 /mis_bots", value="Muestra el estado de tu bot activo.", inline=False)
    embed.add_field(
        name="⚙️ Configuración inicial",
        value=(
            "1. Pon tu token en `BOT_TOKEN`\n"
            "2. *(Opcional)* Pon tu clave Gemini en `GEMINI_API_KEY`\n"
            "3. Ejecuta `python machosting_bot.py`\n"
            "4. Sincroniza comandos con `!sync` (solo admin)"
        ),
        inline=False
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
#  COMANDOS DE PREFIJO (admin)
# ─────────────────────────────────────────────
@bot.command(name="sync")
@commands.is_owner()
async def sync_commands(ctx: commands.Context):
    """Sincroniza los comandos slash globalmente."""
    synced = await bot.tree.sync()
    await ctx.send(f"✅ {len(synced)} comandos sincronizados.")


@bot.command(name="status")
@commands.is_owner()
async def status_cmd(ctx: commands.Context):
    await ctx.send(f"🟢 MacHosting activo | Bots alojados: **{len(hosted_bots)}**")


# ─────────────────────────────────────────────
#  EVENTOS
# ─────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ MacHosting conectado como {bot.user} ({bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(hosted_bots)} bots activos | /panel"
        )
    )
    print("   Usa !sync en Discord para registrar los comandos slash.")


# ─────────────────────────────────────────────
#  INICIO
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if not BOT_TOKEN:
        print("❌ Variable de entorno BOT_TOKEN no configurada.")
        sys.exit(1)
    bot.run(BOT_TOKEN)
