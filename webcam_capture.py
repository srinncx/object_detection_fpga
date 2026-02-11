import cv2

# Open default laptop webcam
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("❌ Cannot open webcam")
    exit()

print("📷 Webcam started. Press 'q' to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ Frame not captured")
        break

    # Get frame size
    h, w, _ = frame.shape

    # Center pixel (OpenCV uses BGR)
    B, G, R = frame[h//2, w//2]

    # Draw center point
    cv2.circle(frame, (w//2, h//2), 5, (0, 255, 0), -1)

    # Display RGB values
    text = f"R={R} G={G} B={B}"
    cv2.putText(frame, text, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1,
                (0, 255, 0), 2)

    cv2.imshow("Webcam Capture", frame)

    print(text)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
