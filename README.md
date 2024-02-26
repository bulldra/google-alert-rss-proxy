## Google Alert RSS 変換プロキシー

-   概要
    -   Google Alert の生成する RSS を Slack / Teams 等から使いやすくするために変換
    -   Google Cloud Functions の利用を想定
-   機能
    -   エントリの URL を参照先に変換し、Slack 等 で URL 展開されるようにする
    -   重複タイトルのエントリを除去（レーベンシュタイン距離で判定）
    -   余計な修飾や情報の削除

## 処理シーケンス

```mermaid
sequenceDiagram
	actor A as User
	participant B1 as Slack
	participant B2 as Slack Server
	box this service
		participant C as Google Alert RSS Proxy
	end
	participant D as Google Alert RSS
	B2->>+C: polling by scheduled
	C->>D: request feed
	D-->>C: response feed
	C->>C: transform feed for slack
	C-->>-B2: response transformed feed
	B2->>B2: check new feed items
	alt new feed items
		B2->>B1: post feed items
		B1->>A: notification
	end
```

## 利用方法

https://{デプロイ URL}?feed={google alert rss}
