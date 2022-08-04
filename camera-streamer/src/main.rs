use tungstenite::{connect, Message, Error as WsError};


fn main() {
    let mut cam = rscam::new("/dev/video0").expect("failed to get camera device");
    // Using default format which should be mjpeg

    cam.start(&rscam::Config {
        interval: (0, 30),
        resolution: (1280, 720),
        format: b"MJPG",
        ..Default::default()
    }).expect("failed to init camera");

    let mut n = 0u32;

    'conn_loop: loop { // Endlessly try to connect
        let (mut sck, _response) = match connect("ws://localhost:11572") {
            Ok(x) => x,
            Err(e) => {println!("failed to connect: {e}"); continue;}
        };
        println!("connected");
        loop { // Endlessly send frames
            let frame = cam.capture().expect("failed to get frame");
            print!("frame {n}\r");
            n += 1;
            match sck.write_message(Message::Binary(frame.into_vec())) {
                Ok(_) => (),
                Err(e) => match e {
                    WsError::AlreadyClosed | WsError::ConnectionClosed => {
                        println!("conn closed, reconnecting");
                        continue 'conn_loop;
                    },
                    _ => println!("error sending frame: {e}")
                }
            }
        }
    }
}
