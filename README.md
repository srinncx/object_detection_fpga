---

# 🎯 FPGA-Based Color Detection Project

This project aims to build an FPGA-accelerated real-time color detection system.

## 📌 Current Progress

At this stage, the project includes:

* ✅ Python program to capture live video from the laptop webcam
* ✅ Display of a center dot on the video frame
* ✅ Pixel value inspection at the center point (to measure RGB range)

The current implementation is focused on understanding image capture and pixel value extraction before moving to hardware acceleration.

---

## 🖥 Technologies Used So Far

* Python
* OpenCV
* NumPy
* Ubuntu Linux

---

## 🚧 Work In Progress

The following components are currently under development:

* 🔄 Sending pixel bitstreams to FPGA using UART
* 🔄 Hardware modeling (Verilog/VHDL)
* 🔄 FPGA-based color detection logic
* 🔄 CPU–FPGA communication pipeline

---

## 🎯 Project Goal

The final objective is to offload image processing tasks from the CPU to an FPGA for faster and more efficient real-time color detection.

---

## 📂 Current Features

* Live webcam feed
* Center reference point for pixel sampling
* Real-time RGB value monitoring

---

More updates will be added as the hardware and communication modules are completed. 🚀
