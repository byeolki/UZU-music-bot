from nextcord import SlashOption, Embed, ChannelType
import nextcord, datetime, pytz, wavelink as nextwave, pafy, sqlite3
from wavelink.ext import spotify
from nextcord.ext import tasks
from nextcord.abc import GuildChannel
from itertools import cycle

intents = nextcord.Intents.all()
client = nextcord.Client(intents=intents)

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

async def node_connect():
    await client.wait_until_ready()
    await nextwave.NodePool.create_node(bot=client, host='lava.link', port=80, password='dismusic', spotify_client=spotify.SpotifyClient(client_id='4a4e4a4a93874eee834a26fbadfc9d17', client_secret='bc721d32e59b4859826440c0422b25f6'))

async def check_voice(user:nextcord.Member, vc: int):
    ch = client.get_channel(vc)
    for i in ch.members:
        if i.id == user.id:
            return True
        else:
            pass
    return False

@client.event
async def on_voice_state_update(member, before=None, after=None):
    voice_state = member.guild.voice_client

    vc : nextwave.Player = voice_state
    if voice_state is None:
        return 

    if len(voice_state.channel.members) == 1:
        await voice_state.disconnect()

    if after.channel is None:
        if f"{vc.guild.id}" in MusicCh.keys():
            MusicCh.pop(member.guild.id)
            Playing.pop(member.guild.id)
        
        vc.queue.clear()

@client.event
async def on_wavelink_node_ready(node : nextwave.Node):
    print(f"{node.identifier} 실행됨")

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
        embed = Embed(description=f"<a:PLAY:1013016922926874654> Now Playing: **{next_song.title}**",color = 0xd561ff,timestamp=datetime.datetime.now(pytz.timezone('UTC')))
        embed.set_author(name=f"{client.name} | Music Playing", icon_url=user.avatar.url)
        embed.add_field(name="시간", value=f"`{video.duration}`", inline=True)
        embed.add_field(name="조회수", value=f"`{video.viewcount:,}`", inline=True)
        embed.add_field(name="업로더", value=f"`{video.author}`", inline=True)
        embed.add_field(name="좋아요", value=f"`{int(video.likes):,}`", inline=True)
        embed.add_field(name="링크", value=f"[클릭하기]({next_song.uri})", inline=True)
        embed.add_field(name="유저", value=f"{user.mention}", inline=True)
        embed.set_thumbnail(url = f"https://img.youtube.com/vi/{next_song.identifier}/mqdefault.jpg")
        await client.get_channel(int(spt[0])).send(embed=embed)
        await vc.play(next_song)

@client.slash_command(description = "음악 재생 또는 재생 목록에 음악을 넣습니다.")
async def 재생(inter : nextcord.Interaction, 검색 : str = SlashOption(description = "검색할 곡을 쓰세요.")): 
    await inter.response.defer()
    try: inter.user.voice.channel
    except: return await inter.send("음성채널에 먼저 들어가주세요!", ephemeral=True)
    try:
        vc : nextwave.Player = await inter.user.voice.channel.connect(cls = nextwave.Player)
    except:
        vc: nextwave.Player = inter.user.guild.voice_client
    if vc.is_playing():
        Playing[inter.guild_id] = True
    elif not vc.is_playing():
        Playing[inter.guild_id] = False
    vc.loop = False
    if len((검색.lower()).split('ttps://')) == 2 and (len((검색.lower()).split('album')) == 2 or len((검색.lower()).split('playlist')) == 2):
        if len((검색.lower()).split('open.spotify.com')) == 2 and len((검색.lower()).split('ttps://')) == 2:
            try:
                if len((검색.lower()).split('album')) == 2:
                    MUSIC = spotify.SpotifyTrack.iterator(query=검색, type=spotify.SpotifySearchType.album)
                elif len((검색.lower()).split('playlist')) == 2:
                    MUSIC = spotify.SpotifyTrack.iterator(query=검색, type=spotify.SpotifySearchType.playlist)   
            except: return await inter.send(":notes: | 앨범 및 플레이 리스트를 찾을 수 없어요!", ephemeral=True) 
        elif len((검색.lower()).split('youtube.com')) == 2 and len((검색.lower()).split('ttps://')) == 2 and len((검색.lower()).split('playlist')) == 2:
            try:
                serch = await vc.node.get_playlist(cls=nextwave.YouTubePlaylist, identifier=검색)
                MUSIC = serch.tracks
            except: return await inter.send(":notes: | 앨범플레이 리스트를 찾을 수 없어요! 플레이 리스트가 비공개 인지 확인해 보세요!", ephemeral=True)
        async for i in MUSIC:
            if Playing[inter.guild.id] is False:
                video = pafy.new(i.uri)
                embed = Embed(description=f"<a:PLAY:1013016922926874654> Now Playing: **{i.title}**",color = 0xd561ff,timestamp=datetime.datetime.now(pytz.timezone('UTC')))
                embed.set_author(name=f"{client.name} | Music Playing", icon_url=inter.user.avatar.url)
                embed.add_field(name="시간", value=f"`{video.duration}`", inline=True)
                embed.add_field(name="조회수", value=f"`{video.viewcount:,}`", inline=True)
                embed.add_field(name="업로더", value=f"`{video.author}`", inline=True)
                embed.add_field(name="좋아요", value=f"`{video.likes:,}`", inline=True)
                embed.add_field(name="링크", value=f"[클릭하기]({i.uri})", inline=True)
                embed.add_field(name="유저", value=f"{inter.user.mention}", inline=True)
                embed.set_thumbnail(url = f"https://img.youtube.com/vi/{i.identifier}/mqdefaulta.jpg")
                await inter.send(embed=embed, content=f":notes: | 남은 곡을 재생목록에 넣는중이에요!")
                MusicCh[inter.guild_id] = f"{inter.channel_id}/{inter.user.id}"
                Playing[inter.guild_id] = True
                await vc.play(i)
            elif Playing[inter.guild.id] is True:
                if await check_voice(user=inter.user, vc=inter.user.voice.channel.id) is True:
                    vc.queue.put(i)
                else:
                    return await inter.send("같은 음성채널에 있어야 봇을 컨트롤 할 수 있어요!", ephemeral=True)
        if vc.is_playing():
            try:
                return await inter.edit_original_message(content=f":notes: | 재생목록에 남은 곡을 추가 했습니다!")
            except:
                return await inter.send(f":notes: | 재생목록에 곡을 추가 했습니다!")
    else:
        try:
            if len((검색.lower()).split('open.spotify.com')) >= 2:
                MUSIC = await spotify.SpotifyTrack.search(query=검색, return_first=True)
            else:
                MUSIC = await nextwave.YouTubeTrack.search(query=검색, return_first=True)
        except:
            await inter.send("검색에 실패 했어요! 오타가 있는지 살펴보세요!", ephemeral=True)
        if Playing[inter.guild.id] is None or Playing[inter.guild.id] is False:
            video = pafy.new(MUSIC.uri)
            vc.loop = False
            embed = Embed(description=f"<a:PLAY:1013016922926874654> Now Playing: **{MUSIC.title}**",color = 0xd561ff,timestamp=datetime.datetime.now(pytz.timezone('UTC')))
            embed.set_author(name=f"{client.name} | Music Playing", icon_url=inter.user.avatar.url)
            embed.add_field(name="시간", value=f"`{video.duration}`", inline=True)
            embed.add_field(name="조회수", value=f"`{video.viewcount:,}`", inline=True)
            embed.add_field(name="업로더", value=f"`{video.author}`", inline=True)
            embed.add_field(name="좋아요", value=f"`{video.likes:,}`", inline=True)
            embed.add_field(name="링크", value=f"[클릭하기]({MUSIC.uri})", inline=True)
            embed.add_field(name="유저", value=f"{inter.user.mention}", inline=True)
            embed.set_thumbnail(url = f"https://img.youtube.com/vi/{MUSIC.identifier}/mqdefault.jpg")
            await inter.send(embed = embed)
            MusicCh[inter.guild_id] = f"{inter.channel_id}/{inter.user.id}"
            await vc.play(MUSIC)
        else:
            try:
                if inter.user.voice.channel.id != inter.guild.me.voice.channel.id:
                    return await inter.send("유저님의 음성 채널 봇의 음성 채널이 달라요!", ephemeral=True)
            except:
                return await inter.send("봇이 음성채널에 없어요!", ephemeral=True)
            if check_voice(user=inter.user, vc=inter.user.voice.channel.id):
                await inter.send(f":notes: | **{MUSIC.title}** 을/를 재생목록에 추가 했습니다")
                await vc.queue.put(MUSIC)
            else:
                return await inter.send("같은 음성채널에 있어야 봇을 컨트롤 할 수 있어요!", ephemeral=True)

@client.slash_command(description = "음악을 일시정지 합니다.")
async def 일시정지(inter : nextcord.Interaction): 
    await inter.response.defer()
    vc : nextwave.Player = inter.guild.voice_client
    if not inter.guild.voice_client:
            return await inter.send("음성채널에 들어가주세요!", ephemeral=True)
    elif not inter.user.voice:
        return await inter.send("음성채널에 들어가주세요!", ephemeral=True)
    try:
        if inter.user.voice.channel.id != inter.guild.me.voice.channel.id:
            return await inter.send("유저님의 음성 채널 봇의 음성 채널이 달라요!", ephemeral=True)
    except:
        return await inter.send("봇이 음성채널에 없어요!", ephemeral=True)
    if vc.is_paused():
        await vc.resume()
        return await inter.send(f"음악이 이미 멈춰 있어요!", ephemeral=True)
    await vc.pause()
    await inter.send(f":notes: | **{vc.track.title}**을/를 일시정지 했습니다!")

@client.slash_command(description = "음악을 다시 재생 합니다.")
async def 다시재생(inter : nextcord.Interaction): 
    await inter.response.defer()
    vc : nextwave.Player = inter.guild.voice_client
    if not inter.guild.voice_client:
            return await inter.send("d음성채널에 들어가주세요!", ephemeral=True)
    elif not inter.user.voice:
        return await inter.send("음성채널에 들어가주세요!", ephemeral=True)
    try:
        if inter.user.voice.channel.id != inter.guild.me.voice.channel.id:
            return await inter.send("유저님의 음성 채널 봇의 음성 채널이 달라요!", ephemeral=True)
    except:
        return await inter.send("봇이 음성채널에 없어요!", ephemeral=True)
    if vc.is_paused():
        await vc.resume()
        return await inter.send(f":notes: | **{vc.track.title}**을/를 다시 재생 했습니다!")
    await vc.pause()
    await inter.send(f"음악이 이미 재생 중이에요!", ephemeral=True)

@client.slash_command(description = "음악을 스킵 합니다.")
async def 스킵(inter : nextcord.Interaction): 
    await inter.response.defer()
    vc : nextwave.Player = inter.guild.voice_client
    if not inter.guild.voice_client:
            return await inter.send("음성채널에 들어가주세요!", ephemeral=True)
    elif not inter.user.voice:
        return await inter.send("음성채널에 들어가주세요!", ephemeral=True)
    try:
        if inter.user.voice.channel.id != inter.guild.me.voice.channel.id:
            return await inter.send("유저님의 음성 채널 봇의 음성 채널이 달라요!", ephemeral=True)
    except:
        return await inter.send("봇이 음성채널에 없어요!", ephemeral=True)
    if vc.queue.is_empty:
        await inter.send("재생 목록이 비었어요!")
    try:
        next_song = vc.queue.get()
    except:
        next_song = vc.queue.get()
    video = pafy.new(next_song.uri)
    embed = Embed(description=f"<a:PLAY:1013016922926874654> Now Playing: **{next_song.title}**",color = 0xd561ff,timestamp=datetime.datetime.now(pytz.timezone('UTC')))
    embed.set_author(name=f"{client.name} | Music Playing", icon_url=inter.user.avatar.url)
    embed.add_field(name="시간", value=f"`{video.duration}`", inline=True)
    embed.add_field(name="조회수", value=f"`{video.viewcount:,}`", inline=True)
    embed.add_field(name="업로더", value=f"`{video.author}`", inline=True)
    embed.add_field(name="좋아요", value=f"`{int(video.likes):,}`", inline=True)
    embed.add_field(name="링크", value=f"[클릭하기]({next_song.uri})", inline=True)
    embed.add_field(name="유저", value=f"{inter.user.mention}", inline=True)
    embed.set_thumbnail(url = f"https://img.youtube.com/vi/{next_song.identifier}/mqdefault.jpg")
    await inter.send(f":notes: | 음악이 스킵됨, 지금 재생: **{next_song.title}**", embed = embed)
    await vc.play(next_song)

@client.slash_command(description = "음악을 반복재생 합니다.")
async def 반복재생(inter : nextcord.Interaction): 
    await inter.response.defer()
    vc : nextwave.Player = inter.guild.voice_client
    if not inter.guild.voice_client:
            return await inter.send("음성채널에 들어가주세요!", ephemeral=True)
    elif not inter.user.voice:
        return await inter.send("음성채널에 들어가주세요!", ephemeral=True)
    try:
        if inter.user.voice.channel.id != inter.guild.me.voice.channel.id:
            return await inter.send("유저님의 음성 채널 봇의 음성 채널이 달라요!", ephemeral=True)
    except:
        return await inter.send("봇이 음성채널에 없어요!", ephemeral=True)
    if not vc.loop:
        vc.loop ^= True
        await inter.send(f":notes: | 이제부터 **{vc.track.title}** 을/를 반복재생 합니다!")
    else:
        setattr(vc, "loop", False)
        vc.loop ^= True
        await inter.send(f":notes: | **{vc.track.title}** 을/를 반복을 비활성화 합니다!")

@client.slash_command(description = "재생목록을 확인 합니다.")
async def 재생목록(inter : nextcord.Interaction): 
    await inter.response.defer()
    vc : nextwave.Player = inter.guild.voice_client
    if vc.queue.is_empty or len(vc.queue) == 1:         
        return await inter.send("재생 목록이 비었거나 1개 밖에 없어요!")
    queue = vc.queue.copy()
    embed = Embed(title="재생 목록!", color = 0xd561ff,timestamp=datetime.datetime.now(pytz.timezone('UTC')))
    view = nextcord.ui.View()
    view.add_item(MusicSelect(queue=queue))
    return await inter.followup.send(embed=embed, view=view) 

class MusicSelect(nextcord.ui.Select):
    def __init__(self , queue):
        option = []
        i = 0
        for music in queue:
            option.append(nextcord.SelectOption(label = music.title , value = music.uri))
            i += 1
        super().__init__(placeholder = "재생목록을 불러왔어요!!" , options = option)
        self.queue = queue

    async def callback(self , inter : nextcord.Interaction):
        MUSIC = self.values[0]
        try:
            MUSIC = await spotify.SpotifyTrack.search(query=MUSIC, return_first=True)
        except:
            MUSIC = await nextwave.YouTubeTrack.search(query=MUSIC, return_first=True)
        video = pafy.new(MUSIC.uri)
        embed = Embed(description=f"<a:PLAY:1013016922926874654> 음악 : **{MUSIC.title}**",color = 0xd561ff,timestamp=datetime.datetime.now(pytz.timezone('UTC')))
        embed.set_author(name=f"{client.name} | Queue", icon_url=inter.user.avatar.url)
        embed.add_field(name="시간", value=f"`{video.duration}`", inline=True)
        embed.add_field(name="조회수", value=f"`{video.viewcount:,}`", inline=True)
        embed.add_field(name="업로더", value=f"`{video.author}`", inline=True)
        embed.add_field(name="좋아요", value=f"`{video.likes:,}`", inline=True)
        embed.add_field(name="링크", value=f"[클릭하기]({MUSIC.uri})", inline=True)
        embed.add_field(name="유저", value=f"{inter.user.mention}", inline=True)
        embed.set_thumbnail(url = f"https://img.youtube.com/vi/{MUSIC.identifier}/mqdefault.jpg")
        await inter.message.edit(embed = embed)
       

client.run('토큰')
