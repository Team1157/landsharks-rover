use std::path::PathBuf;
use tungstenite::{connect, Message, Error as WsError};
use clap::Parser;

#[derive(Parser, Debug)]
#[clap()]
struct Args {
    #[clap(value_parser)]
    device: PathBuf,

    #[clap(short, long, value_parser)]
    framerate: Option<u32>,

    #[clap(short, long, value_parser, number_of_values=2)]
    resolution: Option<Vec<u32>>
}

fn main() {
    let args: Args = Args::parse();

    let mut cam = rscam::new(args.device.to_str().unwrap()).expect("failed to get camera device");

    cam.start(&rscam::Config {
        interval: (1, args.framerate.unwrap_or(10)),
        resolution: args.resolution.map(|v| (v[0], v[1])).unwrap_or((640, 480)),
        format: b"MJPG",
        ..Default::default()
    }).expect("failed to init camera");

    let mut n = 0u32;

    'conn_loop: loop { // Endlessly try to connect
        let (mut sck, _response) = match connect("ws://rover.team1157.org:11572") {
            Ok(x) => x,
            Err(e) => { println!("failed to connect: {e}"); continue; }
        };
        println!("connected");
        loop { // Endlessly send frames
            println!("getting frame");
            let frame = cam.capture().expect("failed to get frame");
            print!("frame {}: {:?}\r", n, frame.format);
            assert_eq!(frame.format, b"MJPG"); // panic if can't get mjpg
            n += 1;
            match sck.write_message(Message::Binary(frame.to_vec())) {
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
