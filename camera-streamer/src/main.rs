use tungstenite::{connect, Message, Error as WsError};
use v4l::prelude::*;
use v4l::{
    Device,
    io::mmap::Stream
};
use v4l::buffer::Type;
use v4l::io::traits::OutputStream;

fn main() {
    let mut cam = Device::new(0).expect("Failed to open camera");
    // Using default format which should be mjpeg

    let mut st = Stream::with_buffers(&mut cam, Type::VideoCapture, 4)
        .expect("Failed to create buffers");

    'conn_loop: loop { // Endlessly try to connect
        let (mut sck, _response) = match connect("ws://localhost:11572") {
            Ok(x) => x,
            Err(e) => {println!("Failed to connect: {e}"); continue;}
        };
        println!("Connected");
        loop { // Endlessly send frames
            let (buf, meta) = st.next().expect("Error getting buffers");
            match sck.write_message(Message::Binary(buf.into())) {
                Ok(_) => (),
                Err(e) => match e {
                    WsError::AlreadyClosed | WsError::ConnectionClosed => {
                        println!("Conn closed, reconnecting");
                        continue 'conn_loop;
                    },
                    _ => println!("Error sending frame: {e}")
                }
            }
        }
    }
}
