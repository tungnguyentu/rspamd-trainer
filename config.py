from environs import Env

env = Env()
env.read_env()

class Settings:
    host = env.str("HOST")
    username = env.str("USERNAME")
    password = env.str("PASSWORD")
    inbox_prefix = env.str("INBOX_PREFIX")
    folder_suffixes = ['spam', 'ham', 'spam_reply']


settings = Settings()