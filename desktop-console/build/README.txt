Agentic Control Console — macOS install notes

If you see a message that the app is damaged or from an unidentified developer, it is Gatekeeper blocking an unsigned app.

1) Move the app to /Applications
2) Remove the quarantine attribute
3) Open the app

Command:
(xattr -dr com.apple.quarantine "/Applications/Agentic Control Console.app")

You can also double-click Unquarantine.command after moving the app to /Applications to run this automatically.
