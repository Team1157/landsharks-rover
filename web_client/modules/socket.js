class Socket {
    constructor(addr: string, port: number) {
        this.socket = new WebSocket(`ws://${addr}:${port}/driver`);
        this.socket.onopen(this.onConnect)
        this.socket.onmessage(this.onMessage)
        this.socket.onclose(this.onDisconnect)
        this.socket.onerror(this.onError)
    }

    async onConnect() {
        let token;
        do {
            token = window.prompt("Please enter your token","");
        } while (token !== "")

    }

    async onMessage() { //TODO
    }

    async onDisconnect() { //TODO
    }

    async onError() { //TODO
    }
}

export { Socket };