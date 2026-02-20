import discord
from discord.ext import commands
import uuid
import json
import os

# ================== CONFIGURAÇÕES ==================
TOKEN = os.getenv("DISCORD_TOKEN")
STAFF_ROLE_ID = 1467027947847417939
TICKET_CATEGORY_ID = 11466945652163612734
MAX_JOGADORES = 2
ARQUIVO_JSON = "painels.json"

# ================== BOT ==================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents)

# ================== MEMÓRIA ==================
painels = {}                 
usuarios_em_ticket = set()   

# ================== JSON ==================
def salvar_painels():
    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(painels, f, indent=4)

def carregar_painels():
    global painels
    if os.path.exists(ARQUIVO_JSON):
        with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
            painels = json.load(f)

# ================== MODAL ==================
class PainelModal(discord.ui.Modal, title="Criar Painel"):
    titulo = discord.ui.TextInput(label="Título")
    texto1 = discord.ui.TextInput(label="Modo")
    texto2 = discord.ui.TextInput(label="Valor")

    async def on_submit(self, interaction: discord.Interaction):
        painel_id = str(uuid.uuid4())
        painels[painel_id] = {"jogadores": []}
        salvar_painels()

        embed = discord.Embed(
            title=self.titulo.value,
            color=discord.Color.from_rgb(255, 0, 0)
        )
        embed.add_field(name="Modo:", value=self.texto1.value, inline=False)
        embed.add_field(name="Valor:", value=self.texto2.value, inline=False)
        embed.add_field(name="Jogadores:", value="Nenhum jogador na fila.", inline=False)

        await interaction.channel.send(embed=embed, view=TicketView(painel_id))
        await interaction.response.send_message("✅ Painel criado!", ephemeral=True)

# ================== VIEW PAINEL ==================
class TicketView(discord.ui.View):
    def __init__(self, painel_id):
        super().__init__(timeout=None)
        self.painel_id = painel_id

    @discord.ui.button(
        label="Entrar",
        style=discord.ButtonStyle.green,
        custom_id="ticket_entrar"
    )
    async def entrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        painel = painels[self.painel_id]

        if interaction.user.id in usuarios_em_ticket:
            return await interaction.response.send_message(
                "❌ Você já está em um ticket ativo.",
                ephemeral=True
            )

        if len(painel["jogadores"]) >= MAX_JOGADORES:
            return await interaction.response.send_message("Ticket cheio.", ephemeral=True)

        painel["jogadores"].append(interaction.user.id)
        usuarios_em_ticket.add(interaction.user.id)
        salvar_painels()

        embed = interaction.message.embeds[0]
        embed.set_field_at(
            2,
            name="Jogadores",
            value="\n".join(f"<@{uid}>" for uid in painel["jogadores"]),
            inline=False
        )
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message("✅ Você entrou!", ephemeral=True)

        if len(painel["jogadores"]) == MAX_JOGADORES:
            await criar_canal_ticket(interaction.guild, painel)

            painel["jogadores"].clear()
            salvar_painels()

            embed.set_field_at(2, name="Jogadores", value="Nenhum jogador na fila.", inline=False)
            await interaction.message.edit(embed=embed)

    @discord.ui.button(
        label="Sair",
        style=discord.ButtonStyle.red,
        custom_id="ticket_sair"
    )
    async def sair(self, interaction: discord.Interaction, button: discord.ui.Button):
        painel = painels[self.painel_id]

        if interaction.user.id not in painel["jogadores"]:
            return await interaction.response.send_message(
                "Você não está na fila.",
                ephemeral=True
            )

        painel["jogadores"].remove(interaction.user.id)
        usuarios_em_ticket.discard(interaction.user.id)
        salvar_painels()

        embed = interaction.message.embeds[0]
        valor = "\n".join(f"<@{uid}>" for uid in painel["jogadores"]) or "Nenhum jogador na fila."
        embed.set_field_at(2, name="Jogadores", value=valor, inline=False)
        await interaction.message.edit(embed=embed)

        await interaction.response.send_message("❌ Você saiu.", ephemeral=True)

# ================== VIEW FECHAR ==================
class FecharTicketView(discord.ui.View):
    @discord.ui.button(label="Finalizar Ticket", style=discord.ButtonStyle.red)
    async def fechar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if STAFF_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message(
                "Apenas a staff pode fechar.",
                ephemeral=True
            )

        for member in interaction.channel.members:
            usuarios_em_ticket.discard(member.id)

        await interaction.channel.delete()

# ================== CANAL ==================
async def criar_canal_ticket(guild, painel):
    category = guild.get_channel(TICKET_CATEGORY_ID)
    staff_role = guild.get_role(STAFF_ROLE_ID)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        staff_role: discord.PermissionOverwrite(view_channel=True)
    }

    for uid in painel["jogadores"]:
        member = guild.get_member(uid)
        if member:
            overwrites[member] = discord.PermissionOverwrite(view_channel=True)

    channel = await guild.create_text_channel(
        name="ticket-jogo",
        category=category,
        overwrites=overwrites
    )

    mencoes = " ".join(f"<@{uid}>" for uid in painel["jogadores"])

    await channel.send(
        f"🎮 **Ticket criado!**\n{mencoes}",
        view=FecharTicketView()
    )

# ================== COMANDO ==================
@bot.tree.command(name="painel")
async def painel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Sem permissão.", ephemeral=True)
    await interaction.response.send_modal(PainelModal())

# ================== READY ==================
@bot.event
async def on_ready():
    carregar_painels()

    for painel_id in painels.keys():
        bot.add_view(TicketView(painel_id))

    await bot.tree.sync()
    print(f"✅ Bot online: {bot.user}")

# ================== RUN ==================
bot.run(TOKEN)