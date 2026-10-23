"""
Unit test for ReadMoreExpander (WhatsApp message expander).
"""

import os
from PIL import Image, ImageDraw
from app.capture.read_more_expander import ReadMoreExpander

def test_detect_whatsapp_read_more_synthetic_image():
    expander = ReadMoreExpander()

    # Create dark-mode WhatsApp synthetic message bubble (1200x800)
    # Background: #111b21, Text: #25d366 (WhatsApp link green)
    img = Image.new("RGB", (1200, 800), color=(17, 27, 33))
    draw = ImageDraw.Draw(img)

    # Draw white text simulating message body in chat pane (x=450, y=200)
    draw.rectangle([450, 200, 800, 215], fill=(240, 240, 240))
    draw.rectangle([450, 225, 750, 240], fill=(240, 240, 240))

    # Draw simulated green "... Read more" link
    # "... " dots in light gray
    draw.rectangle([450, 260, 465, 272], fill=(180, 180, 180))
    # "Read more" in WhatsApp vibrant green (#25D366 -> RGB 37, 211, 102)
    draw.rectangle([475, 258, 550, 275], fill=(37, 211, 102))

    coords = expander.find_read_more_coordinates(img, screen_offset=(100, 50))

    assert len(coords) >= 1
    cx, cy = coords[0]
    # Check that coordinate falls within the drawn green rectangle + offset
    # X: 100 + [475..550] -> 575..650
    # Y: 50 + [258..275] -> 308..325
    assert 560 <= cx <= 660
    assert 300 <= cy <= 335

def test_detect_user_uploaded_read_more_if_available():
    user_img_path = r"C:\Users\murtu\.gemini\antigravity-ide\brain\f77adb4a-3e77-456e-81b7-ebb51aee1889\.user_uploaded\media_1792514947250.png"
    if os.path.exists(user_img_path):
        img = Image.open(user_img_path)
        expander = ReadMoreExpander()
        coords = expander.find_read_more_coordinates(img)
        assert len(coords) >= 1

def test_cooldown_reset_on_scroll():
    expander = ReadMoreExpander()
    img = Image.new("RGB", (1200, 800), color=(17, 27, 33))
    draw = ImageDraw.Draw(img)
    draw.rectangle([475, 258, 550, 275], fill=(37, 211, 102))

    coords1 = expander.find_read_more_coordinates(img, screen_offset=(0, 0))
    assert len(coords1) >= 1
    cx, cy = coords1[0]
    expander._mark_clicked(cx, cy)

    # Immediately checking again should be suppressed by cooldown
    assert expander._is_recently_clicked(cx, cy)

    # When scroll occurs, reset_cooldown clears click history so new messages at same coordinate are clicked
    expander.reset_cooldown()
    assert not expander._is_recently_clicked(cx, cy)

def test_cyan_blue_read_more_detection():
    expander = ReadMoreExpander()
    # WhatsApp Web / Chrome Cyan link color
    img = Image.new("RGB", (1200, 800), color=(17, 27, 33))
    draw = ImageDraw.Draw(img)
    # Cyan link (RGB: 83, 189, 235 -> #53BDEB)
    draw.rectangle([500, 300, 580, 318], fill=(83, 189, 235))

    coords = expander.find_read_more_coordinates(img, screen_offset=(0, 0))
    assert len(coords) >= 1
