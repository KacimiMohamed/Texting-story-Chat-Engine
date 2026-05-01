import requests
from django.conf import settings
from django.core.files.base import ContentFile
from .models import Story


def generate_story_audio(story_id: int):
    story = Story.objects.get(id=story_id)
    messages = story.messages.all().order_by('order')
    
    api_key = getattr(settings, 'ELEVENLABS_API_KEY', None)
    if not api_key:
        print("Error: ELEVENLABS_API_KEY not found in settings.")
        return

    for msg in messages:
        # Skip if it already has audio or has no text
        if msg.audio_file or not msg.text:
            continue
            
        print(f"Generating audio for message {msg.id}...")
        voice_id = msg.character.elevenlabs_voice_id
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        
        data = {
            "text": msg.text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            # Save the binary audio directly into the Django FileField
            file_name = f"story_{story.id}_msg_{msg.id}.mp3"
            msg.audio_file.save(file_name, ContentFile(response.content), save=True)
            print(f"✅ Saved: {file_name}")
        else:
            print(f"❌ Failed: {response.text}")
