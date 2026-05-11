---
description: canonical single static block allows
verdict: allow
payload: write
---
class Config {
  static endpoint: string;
  static {
    Config.endpoint = 'https://api.example.com'
  }
}

