from contextvars import Context
import sqlite3, discord as nextcord, datetime, pytz, pycord.wavelink as nextwave, pafy
from discord import Embed, Interaction, ButtonStyle, ui, Member
from wavelink.ext import spotify
from discord.ext import tasks, commands
from itertools import cycle
from discord.ui import View, Button 
from discord.commands import Option as SlashOption

intents = nextcord.Intents.all()
client = commands.Bot(intents=intents)

MusicMsg = {}   
MusicCh = {}
Playing = {}

@client.event
async def on_ready():
    status = cycle([f"{len(client.users)}명과 함께하는", f"{len(client.guilds)}개의 서버에 참여하는", f"노래 부르는"])
    i = datetime.datetime.now()
    print(f"{client.user.name}봇은 준비가 완료 되었습니다.")
    print(f"[!] 참가 중인 서버 : {len(client.guilds)}개의 서버에 참여 중")  
    print(f"[!] 이용자 수 : {len(client.users)}와 함께하는 중")
    change_status.start(status)
    client.loop.create_task(node_connect())
    guild_list = client.guilds
    for i in guild_list:
        print("서버 ID: {} / 서버 이름: {} / 멤버 수: {}".format(i.id, i.name, i.member_count))
    
@tasks.loop(seconds=5)
async def change_status(status):
    await client.change_presence(activity=nextcord.Streaming(name=next(status), url='https://www.twitch.tv/your_channel_here'))

@client.event
async def on_voice_state_update(member, before=None, after=None):
    voice_state = member.guild.voice_client

    vc : nextwave.Player = voice_state
    if voice_state is None:
        return 

    if len(voice_state.channel.members) == 1:
        await vc.pause()
    
    elif len(voice_state.channel.members) > 1:
        await vc.resume()

    if after.channel is None:
        if f"{vc.guild.id}" in MusicCh.keys():
            MusicCh.pop(member.guild.id)
            Playing.pop(member.guild.id)
        
        vc.queue.clear()

@client.event
async def on_wavelink_node_ready(node : nextwave.Node):
    print(f"{node.identifier} 실행됨")


async def node_connect():
    await client.wait_until_ready()
    await nextwave.NodePool.create_node(bot=client, host='lava.link', port=80, password='dismusic', spotify_client=spotify.SpotifyClient(client_id='4a4e4a4a93874eee834a26fbadfc9d17', client_secret='bc721d32e59b4859826440c0422b25f6'))

async def check_voice(user:nextcord.Member, vc: int):
    try: user.voice.channel
    except: return False
    ch = client.get_channel(vc)
    for i in ch.members:
        if i.id == user.id:
            return True
        else:
            pass
    return False

def embed_maker(array, user_id):
    user = client.get_user(user_id)
    video = pafy.new(array.uri)
    embed = Embed(description=f"<a:PLAY:1021777473161134120> Now Playing: **{array.title}**",color = 0xd561ff,timestamp=datetime.datetime.now(pytz.timezone('UTC')))
    embed.set_author(name="UZU | Music Playing", icon_url=user.avatar.url)
    embed.add_field(name="시간", value=f"`{video.duration}`", inline=True)
    embed.add_field(name="조회수", value=f"`{video.viewcount:,}`", inline=True)
    embed.add_field(name="업로더", value=f"`{video.author}`", inline=True)
    try : embed.add_field(name="좋아요", value=f"`{int(video.likes):,}`", inline=True)
    except: pass
    embed.add_field(name="링크", value=f"[클릭하기]({array.uri})", inline=True)
    embed.add_field(name="유저", value=f"{user.mention}", inline=True)
    embed.set_thumbnail(url = f"https://img.youtube.com/vi/{array.identifier}/mqdefault.jpg")
    return embed
    
@client.event
async def on_wavelink_track_end(player : nextwave.Player , track : nextwave.Track , reason):
    if reason != "REPLACED":
        vc : nextwave.Player = player.guild.voice_client
        if vc.loop:
            return await vc.play(track)
        if vc.queue.is_empty:
            MusicCh.pop(player.guild.id)
            Playing.pop(player.guild.id)
            return await vc.disconnect()
        next_song = vc.queue.get()
        video = pafy.new(next_song.uri)
        spt = MusicCh[player.guild.id].split('/')
        user = client.get_user(int(spt[1]))
        ch = client.get_channel(int(spt[0]))
        msg = await ch.fetch_message(MusicMsg[player.guild.id]); await msg.delete()
        await ch.send(embed=embed_maker(user_id=int(spt[1]), array=next_song), view=MusicPlayer(vc=vc))
        await vc.play(next_song)
        MusicMsg[player.guild_id] = msg.id
    else:
      msg = await ch.fetch_message(MusicMsg[player.guild.id])
      await msg.delete()

@client.slash_command(description = "테스트 커맨드")
async def 테스트(inter):
    for emoji in inter.guild.emojis:
        print(emoji.name, " : ", emoji.id) 

@client.slash_command(description = "음악 재생 또는 재생 목록에 음악을 넣습니다.")
async def 재생(inter: Context, 검색 : SlashOption(str, description = "검색할 곡을 쓰세요.")): 
    await inter.response.defer()
    if await check_voice(user=inter.author, vc=inter.author.voice.channel.id) is False:
        return await inter.respond("같은 음성채널에 있어야 봇을 컨트롤 할 수 있어요!", ephemeral=True)
    try:
        vc : nextwave.Player = await inter.author.voice.channel.connect(cls = nextwave.Player)
    except:
        vc: nextwave.Player = inter.author.guild.voice_client
    if vc.is_playing():
        Playing[inter.guild_id] = True
    elif not vc.is_playing():
        Playing[inter.guild_id] = False
    else:
        Playing[inter.guild_id] = False
    vc.loop = False
    if len((검색.lower()).split('ttps://')) == 2 and (len((검색.lower()).split('album')) == 2 or len((검색.lower()).split('playlist')) == 2):
        if len((검색.lower()).split('open.spotify.com')) == 2 and len((검색.lower()).split('ttps://')) == 2:
            try:
                if len((검색.lower()).split('album')) == 2:
                    MUSIC = spotify.SpotifyTrack.iterator(query=검색, type=spotify.SpotifySearchType.album)
                elif len((검색.lower()).split('playlist')) == 2:
                    MUSIC = spotify.SpotifyTrack.iterator(query=검색, type=spotify.SpotifySearchType.playlist)   
            except: return await inter.respond(":notes: | 앨범 및 플레이 리스트를 찾을 수 없어요!", ephemeral=True)
            async for i in MUSIC:
                if Playing[inter.guild.id] is False:
                    await vc.play(i)
                    msg = await inter.respond(embed=embed_maker(user_id=inter.author.id, array=MUSIC), content=f":notes: | 남은 곡을 재생목록에 넣는중이에요!", view=MusicPlayer(vc=vc))
                    MusicCh[inter.guild_id] = f"{inter.channel_id}/{inter.author.id}";Playing[inter.guild_id] = True;MusicMsg[inter.guild_id] = msg.id
                elif Playing[inter.guild.id] is True:
                    vc.queue.put(i) 
            
        elif len((검색.lower()).split('youtube.com')) == 2 and len((검색.lower()).split('ttps://')) == 2 and len((검색.lower()).split('playlist')) == 2:
            try:
                #await inter.respond("유튜브 플레이리스트를 재생하는데 문제가 있어 해결중이에요! 조금만 기다려주세요!", ephemeral=True)
                serch = await vc.node.get_playlist(cls=nextwave.YouTubePlaylist, identifier=검색)
                MUSIC = serch.tracks
            except: return await inter.respond(":notes: | 앨범플레이 리스트를 찾을 수 없어요! 플레이 리스트가 비공개 인지 확인해 보세요!", ephemeral=True)
            for i in MUSIC:
                if Playing[inter.guild.id] is False:
                    await vc.play(i)
                    msg = await inter.respond(embed=embed_maker(user_id=inter.author.id, array=MUSIC), content=f":notes: | 남은 곡을 재생목록에 넣는중이에요!", view=MusicPlayer(vc=vc))
                    MusicCh[inter.guild_id] = f"{inter.channel_id}/{inter.author.id}"; Playing[inter.guild_id] = True;MusicMsg[inter.guild_id] = msg.id
                elif Playing[inter.guild.id] is True:
                    vc.queue.put(i)
        if vc.is_playing():
            try:
                return await inter.edit_original_message(content=f":notes: | 재생목록에 남은 곡을 추가 했습니다!")
            except:
                return await inter.respond(f":notes: | 재생목록에 곡을 추가 했습니다!")
    else:
        try:
            if len((검색.lower()).split('open.spotify.com')) >= 2:
                MUSIC = await spotify.SpotifyTrack.search(query=검색, return_first=True)
            else:
                MUSIC = await nextwave.YouTubeTrack.search(query=검색, return_first=True)
        except:
            MUSIC = await nextwave.YouTubeTrack.search(query=검색, return_first=True)
        if Playing[inter.guild.id] is False:
            await vc.play(MUSIC)
            msg = await inter.respond(embed = embed_maker(array=MUSIC, user_id=inter.author.id) , view = MusicPlayer(vc = vc))
            MusicCh[inter.guild_id] = f"{inter.channel_id}/{inter.author.id}";MusicMsg[inter.guild_id] = msg.id;Playing[inter.guild_id] = True
        else:
            try:
                if inter.author.voice.channel.id != inter.guild.me.voice.channel.id:
                    return await inter.respond("유저님의 음성 채널 봇의 음성 채널이 달라요!", ephemeral=True)
            except:
                return await inter.respond("봇이 음성채널에 없어요!", ephemeral=True)
            if check_voice(user=inter.author, vc=inter.author.voice.channel.id):
                await inter.respond(f":notes: | **{MUSIC.title}** 을/를 재생목록에 추가 했습니다")
                vc.queue.put(MUSIC)
            else:
                return await inter.respond("같은 음성채널에 있어야 봇을 컨트롤 할 수 있어요!", ephemeral=True)

@client.slash_command(description = "음악을 일시정지 합니다.")
async def 일시정지(inter: Context): 
    await inter.response.defer()
    vc : nextwave.Player = inter.guild.voice_client
    if not inter.guild.voice_client:
            return await inter.respond("음성채널에 들어가주세요! 또는 봇을 음성채널에 초대해주세요!", ephemeral=True)
    elif not inter.author.voice:
        return await inter.respond("음성채널에 들어가주세요!", ephemeral=True)
    try:
        if inter.author.voice.channel.id != inter.guild.me.voice.channel.id:
            return await inter.respond("유저님의 음성 채널 봇의 음성 채널이 달라요!", ephemeral=True)
    except:
        return await inter.respond("봇이 음성채널에 없어요!", ephemeral=True)
    if vc.is_paused():
        return await inter.respond(f"음악이 이미 멈춰 있어요!", ephemeral=True)
    await vc.pause()
    await inter.respond(f":notes: | **{vc.track.title}**을/를 일시정지 했습니다!")

@client.slash_command(description = "음악을 다시 재생 합니다.")
async def 다시재생(inter: Context): 
    await inter.response.defer()
    vc : nextwave.Player = inter.guild.voice_client
    if not inter.guild.voice_client:
            return await inter.respond("음성채널에 들어가주세요!", ephemeral=True)
    elif not inter.author.voice:
        return await inter.respond("음성채널에 들어가주세요!", ephemeral=True)
    try:
        if inter.author.voice.channel.id != inter.guild.me.voice.channel.id:
            return await inter.respond("유저님의 음성 채널 봇의 음성 채널이 달라요!", ephemeral=True)
    except:
        return await inter.respond("봇이 음성채널에 없어요!", ephemeral=True)
    if vc.is_paused():
        await vc.resume()
        return await inter.respond(f":notes: | **{vc.track.title}**을/를 다시 재생 했습니다!")
    await inter.respond(f"음악이 이미 재생 중이에요!", ephemeral=True)

@client.slash_command(description = "음악을 스킵 합니다.")
async def 스킵(inter: Context): 
    await inter.response.defer()
    vc : nextwave.Player = inter.guild.voice_client
    if not inter.guild.voice_client:
            return await inter.respond("음성채널에 들어가주세요!", ephemeral=True)
    elif not inter.author.voice:
        return await inter.respond("음성채널에 들어가주세요!", ephemeral=True)
    try:
        if inter.author.voice.channel.id != inter.guild.me.voice.channel.id:
            return await inter.respond("유저님의 음성 채널 봇의 음성 채널이 달라요!", ephemeral=True)
    except:
        return await inter.respond("봇이 음성채널에 없어요!", ephemeral=True)
    if vc.queue.is_empty:
        await inter.respond("재생 목록이 비었어요!")
    try:
        next_song = vc.queue.get()
    except:
        next_song = vc.queue.get()
    video = pafy.new(next_song.uri)
    embed = Embed(description=f"<a:PLAY:1021777473161134120> Now Playing: **{next_song.title}**",color = 0xd561ff,timestamp=datetime.datetime.now(pytz.timezone('UTC')))
    embed.set_author(name="UZU | Music Playing", icon_url=inter.author.avatar.url)
    embed.add_field(name="시간", value=f"`{video.duration}`", inline=True)
    embed.add_field(name="조회수", value=f"`{video.viewcount:,}`", inline=True)
    embed.add_field(name="업로더", value=f"`{video.author}`", inline=True)
    embed.add_field(name="좋아요", value=f"`{int(video.likes):,}`", inline=True)
    embed.add_field(name="링크", value=f"[클릭하기]({next_song.uri})", inline=True)
    embed.add_field(name="유저", value=f"{inter.author.mention}", inline=True)
    embed.set_thumbnail(url = f"https://img.youtube.com/vi/{next_song.identifier}/mqdefault.jpg")
    view = View()
    view.add_item(MusicPlayer(vc=vc))
    msg = await inter.respond(f":notes: | 음악이 스킵됨, 지금 재생: **{next_song.title}**", embed = embed,view=view)
    MusicMsg[inter.guild_id] = msg.id
    await vc.play(next_song)

@client.slash_command(description = "음악을 반복재생 합니다.")
async def 반복재생(inter: Context): 
    await inter.response.defer()
    vc : nextwave.Player = inter.guild.voice_client
    if not inter.guild.voice_client:
            return await inter.respond("음성채널에 들어가주세요!", ephemeral=True)
    elif not inter.author.voice:
        return await inter.respond("음성채널에 들어가주세요!", ephemeral=True)
    try:
        if inter.author.voice.channel.id != inter.guild.me.voice.channel.id:
            return await inter.respond("유저님의 음성 채널 봇의 음성 채널이 달라요!", ephemeral=True)
    except:
        return await inter.respond("봇이 음성채널에 없어요!", ephemeral=True)
    if not vc.loop:
        vc.loop ^= True
        await inter.respond(f":notes: | 이제부터 **{vc.track.title}** 을/를 반복재생 합니다!")
    else:
        setattr(vc, "loop", False)
        vc.loop ^= True
        await inter.respond(f":notes: | **{vc.track.title}** 을/를 반복을 비활성화 합니다!")

@client.slash_command(description = "재생목록을 확인 합니다.")
async def 재생목록(inter: Context): 
    await inter.response.defer()
    try:
        vc : nextwave.Player = inter.guild.voice_client
        if vc.queue.is_empty or len(vc.queue) == 1:         
            return await inter.respond("재생 목록이 비었거나 1개 밖에 없어요!")
        queue = vc.queue.copy()
        embed = Embed(title="재생 목록!", color = 0xd561ff,timestamp=datetime.datetime.now(pytz.timezone('UTC')))
        view = nextcord.ui.View()
        view.add_item(QueueMusic(queue=queue))
        await inter.followup.respond(embed=embed, view=view) 
    except:
        await inter.respond("아직 재생목록을 불러오지 못 했어요!")

class QueueMusic(nextcord.ui.Select):
    def __init__(self , queue):
        option = []
        for music in queue:
            option.append(nextcord.SelectOption(label = music.title , value = music.uri))
        super().__init__(placeholder = "재생목록을 불러왔어요!!" , options = option)
        self.queue = queue

    async def callback(self , inter):
        try:
            MUSIC = self.values[0]
            try:
                MUSIC = await spotify.SpotifyTrack.search(query=MUSIC, return_first=True)
            except:
                MUSIC = await nextwave.YouTubeTrack.search(query=MUSIC, return_first=True)
            video = pafy.new(MUSIC.uri)
            embed = Embed(description=f"<a:PLAY:1021777473161134120> 음악 : **{MUSIC.title}**",color = 0xd561ff,timestamp=datetime.datetime.now(pytz.timezone('UTC')))
            embed.set_author(name="UZU | Queue", icon_url=inter.author.avatar.url)
            embed.add_field(name="시간", value=f"`{video.duration}`", inline=True)
            embed.add_field(name="조회수", value=f"`{video.viewcount:,}`", inline=True)
            embed.add_field(name="업로더", value=f"`{video.author}`", inline=True)
            embed.add_field(name="좋아요", value=f"`{video.likes:,}`", inline=True)
            embed.add_field(name="링크", value=f"[클릭하기]({MUSIC.uri})", inline=True)
            embed.add_field(name="유저", value=f"{inter.author.mention}", inline=True)
            embed.set_thumbnail(url = f"https://img.youtube.com/vi/{MUSIC.identifier}/mqdefault.jpg")
            await inter.message.edit(embed = embed, view= None)
        except:
            await inter.message.edit("음악을 불러오지 못 했어요!")

class MusicModal(ui.Modal):
    def __init__(self , vc : nextwave.Player):
        super().__init__("음악 추가!")
        self.music = ui.TextInput(label = "추가할 곡을 입력하세요" , placeholder = "여기에 입력해주세요!")
        self.vc = vc
        self.add_item(self.music)
    async def callback(self, inter : Interaction):
        array = await nextwave.YouTubeTrack.search(query = self.music.value , return_first = True)
        self.vc.queue.put(array)
        await inter.respond(f":notes: | **{array.title}**을 재생목록에 곡을 추가 했습니다!")

class MusicPlayer(ui.View):
    def __init__(self , vc : nextwave.Player):
        super().__init__(timeout = None)
        self.vc = vc

    @ui.button(style = ButtonStyle.gray, emoji = "<:play_pause:1021776393975111740>")
    async def pause_resume(self , button : ui.Button , inter : Interaction):
        if check_voice(vc=self.vc.channel.id, user = inter.user) is True:
            try: self.vc.track.title
            except: await inter.send("음악이 재생되고 있지 않습니다!")
            if self.vc.is_paused():
              await self.vc.resume()
              return await inter.send(f":notes: | **{self.vc.track.title}**을/를 다시재생 했습니다!")
            await self.vc.pause()
            await inter.send(f":notes: | **{self.vc.track.title}**을/를 일시정지 했습니다!")
        else:
            await inter.send("봇과 같은 음성채널에 입장해주세요!", ephemeral = True)
          
    @ui.button(style = ButtonStyle.gray, emoji = "<:queue:1021776396202299452>")
    async def playlist(self , button : ui.Button , inter : Interaction):
        if check_voice(vc=self.vc.channel.id, user = inter.user) is True:
          if self.vc.queue.is_empty: 
            return await inter.send("재생 목록 비었어요!")
          queue = self.vc.queue.copy()
          embed = Embed(title="재생 목록!", color = 0xd561ff,timestamp=datetime.datetime.now(pytz.timezone('UTC')))
          await inter.followup.send(embed=embed, view=QueueMusic(queue=queue))
        # await inter.send("개발중인 기능이에요! **/재생목록**으로 확인해주세요!", ephemeral = True)
        else:
            await inter.send("봇과 같은 음성채널에 입장해주세요!", ephemeral = True)

    @ui.button(style = ButtonStyle.gray , emoji="<:playlist_add:1021776391609532427>")
    async def playlist_add(self , button : ui.Button , inter : Interaction):
        if check_voice(vc=self.vc.channel.id, user = inter.user) is True:
            await inter.send_modal(MusicModal(vc = self.vc))
        else:
            await inter.send("봇과 같은 음성채널에 입장해주세요!", ephemeral = True)

    @ui.button(style = ButtonStyle.gray , emoji = "<:skip_next:1021776398748242030>")
    async def skip(self , button : ui.Button , inter : Interaction):
        if check_voice(vc=self.vc.channel.id, user = inter.user) is True:
            if self.vc.queue.is_empty:
                await inter.send("재생 목록이 비었어요!")
            try:
                next_song = self.vc.queue.get()
            except:
                next_song = self.vc.queue.get()
            await self.vc.play(next_song)
            msg = await inter.send(f":notes: | 음악이 스킵됨, 지금 재생: **{next_song.title}**", embed = embed_maker(array=next_song, user_id=inter.user.id))
            MusicMsg[inter.guild_id] = msg.id
        else:
            await inter.send("봇과 같은 음성채널에 입장해주세요!", ephemeral = True)
    
    @ui.button(style = ButtonStyle.red , emoji = "<:stop:1021776400979595345>")
    async def stop(self , button : ui.Button , inter : Interaction):
        if check_voice(vc=self.vc.channel.id, user = inter.user) is True:
            await self.vc.disconnect()
            await inter.send("음악 재생을 종료합니다!")
        else:
            await inter.send("봇과 같은 음성채널에 입장해주세요!", ephemeral = True)

TOKEN = 토큰
client.run(TOKEN)
