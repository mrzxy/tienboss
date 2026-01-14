import discord
from discord.ext import commands
import asyncio
import logging

# 设置日志级别以查看更多调试信息
logging.basicConfig(level=logging.DEBUG)

# 你的普通用户 Token (请勿泄露给任何人)
USER_TOKEN = ''

# 你想要加入的语音频道 ID (右键频道 -> 复制ID)
VOICE_CHANNEL_ID = 1404733922159497311

class MySelfBot(discord.Client):
    async def on_ready(self):
        print(f'已登录为: {self.user} (ID: {self.user.id})')

        # 打印所有可访问的服务器和语音频道
        print(f'\n可访问的服务器数量: {len(self.guilds)}')
        for guild in self.guilds:
            print(f'\n服务器: {guild.name} (ID: {guild.id})')
            voice_channels = [ch for ch in guild.channels if isinstance(ch, (discord.VoiceChannel, discord.StageChannel))]
            if voice_channels:
                print(f'  语音频道:')
                for vc in voice_channels:
                    print(f'    - {vc.name} (ID: {vc.id})')

        print('\n正在尝试加入语音频道...')

        try:
            # 获取频道对象
            channel = self.get_channel(VOICE_CHANNEL_ID)

            if not channel:
                print(f"错误: 找不到指定的频道 (ID: {VOICE_CHANNEL_ID})")
                print("提示: 确保你的账号能访问该频道所在的服务器")
                print("请检查上面列出的可用语音频道ID")
                return

            if isinstance(channel, discord.VoiceChannel) or isinstance(channel, discord.StageChannel):
                print(f"频道类型: {type(channel).__name__}")
                print(f"频道名称: {channel.name}")
                print("开始连接...")

                # 加入频道
                # self_mute=True, self_deaf=True 可以模拟静音和拒听，降低被检测风险
                voice_client = await channel.connect(self_mute=True, self_deaf=True, timeout=30.0, reconnect=False)

                print(f"✅ 成功加入频道: {channel.name}")
                print(f"语音客户端: {voice_client}")
                print("保持连接中... (按 Ctrl+C 退出)")
            else:
                print("错误: 该 ID 不是一个语音频道。")

        except IndexError as e:
            print(f"\n❌ 发生错误: list index out of range")
            print("详细错误:", e)
            print("\n可能的原因:")
            print("1. discord.py 库与用户账号（self-bot）不完全兼容")
            print("2. 某些语音协议参数可能不适用于用户账号")
            print("3. Discord 可能限制了用户账号的语音连接功能")
            print("\n完整错误堆栈:")
            import traceback
            traceback.print_exc()
            print("\n建议: 考虑使用官方 Bot 账号而非用户账号")
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            print(f"错误类型: {type(e).__name__}")
            print("\n完整错误堆栈:")
            import traceback
            traceback.print_exc()

    # 防止脚本因为网络波动断开，保持运行
    async def on_voice_state_update(self, member, before, after):
        # 这里可以写逻辑：如果你被踢出了，自动重新加入
        if member.id == self.user.id and after.channel is None:
            print("检测到断开连接，准备重连...")
            # 实际重连逻辑需要小心编写，避免造成死循环被封号

client = MySelfBot()
client.run(USER_TOKEN)