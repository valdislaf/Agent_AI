import pyttsx3

engine = pyttsx3.init("sapi5")
voices = engine.getProperty("voices")
print("voices:", [v.name for v in voices])

# выбрать русский голос, если есть
for v in voices:
    if "Irina" in v.name or "Russian" in v.name:
        engine.setProperty("voice", v.id)
        break

engine.setProperty("rate", 170)
engine.setProperty("volume", 1.0)
engine.say("Привет, я говорю")
engine.runAndWait()
