use std::error::Error;
use std::io::Cursor;
use std::path::PathBuf;
use tungstenite::{connect, Message, Error as WsError};
use clap::Parser;
use image::io::Reader as ImageReader;

#[derive(Parser, Debug)]
#[clap()]
struct Args {
    #[clap(value_parser)]
    device: PathBuf,

    #[clap(short, long, value_parser)]
    framerate: Option<u32>,

    #[clap(short, long, value_parser, number_of_values=2)]
    input_resolution: Option<Vec<u32>>,

    #[clap(short='r', long, value_parser, number_of_values=2)]
    output_resolution: Option<Vec<u32>>,

    #[clap(short='q', long, value_parser)]
    output_quality: Option<u8>,

    #[clap(short='e', long)]
    reencode: bool,

    #[clap(short, long)]
    debug: bool
}


fn main() {
    // Parse args
    let args: Args = Args::parse();
    let input_res = args.input_resolution.map(|v| (v[0], v[1])).unwrap_or((640, 480));
    let output_res = args.output_resolution.map(|v| (v[0], v[1])).unwrap_or((256, 144));
    let output_qual = args.output_quality.unwrap_or(50);
    let debug = args.debug;
    let reencode = args.reencode;

    // get camera device, config and start
    let mut cam = rscam::new(args.device.to_str().unwrap()).expect("failed to get camera device");

    cam.start(&rscam::Config {
        interval: (1, args.framerate.unwrap_or(10)),
        resolution: input_res,
        format: b"MJPG",
        ..Default::default()
    }).expect("failed to init camera");

    let mut n = 0u32;

    'conn_loop: loop { // Endlessly try to connect
        let (mut sck, _response) = match connect("ws://rover.team1157.org:11572/stream") {
            Ok(x) => x,
            Err(e) => { println!("failed to connect: {e}"); continue; }
        };
        println!("connected");
        loop { // Endlessly send frames
            if debug { println!("getting frame"); }
            let frame = cam.capture().expect("failed to get frame");
            if debug { println!("frame {}: {}, size {}", n, std::str::from_utf8(&frame.format).unwrap(), frame.len()); }
            assert_eq!(frame.format, *b"MJPG"); // panic if can't get mjpg
            n += 1;
            let msg = if reencode {
                // reencode frame
                let encoded_frame = match reencode_frame(
                    &frame,
                    output_res,
                    output_qual
                ) {
                    Ok(f) => f,
                    Err(e) => {
                        println!("Failed to reencode frame: {}", e);
                        continue
                    }
                };
                if debug { println!("reencoded to size {}", encoded_frame.len()) }
                Message::Binary(encoded_frame)
            }
            else {
                Message::Binary(frame.as_vec())
            };
            match sck.write_message(msg) {
                Ok(_) => (),
                Err(e) => match e {
                    WsError::AlreadyClosed | WsError::ConnectionClosed | WsError::Io(_) => {
                        println!("conn closed, reconnecting");
                        continue 'conn_loop;
                    },
                    _ => println!("error sending frame: {e}")
                }
            }
        }
    }
}

fn reencode_frame(frame: &[u8], size: (u32, u32), quality: u8) -> Result<Vec<u8>, Box<dyn Error>> {
    let mut out = Vec::<u8>::new();
    ImageReader::new(Cursor::new(frame))
        .with_guessed_format()?
        .decode()?
        .resize(size.0, size.1, image::imageops::FilterType::Lanczos3)
        .write_to(&mut Cursor::new(&mut out), image::ImageOutputFormat::Jpeg(quality))?;
    Ok(out)
}
