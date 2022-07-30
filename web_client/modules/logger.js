let callbacks, broadcastCallbacks;

export function initLogger(callbacksLocal, broadcastCallbacksLocal) {
    callbacks = callbacksLocal;
    broadcastCallbacks = broadcastCallbacksLocal;
}

/**
* Logs a message to the console and broadcasts it to the base station if desired
*
* @param {string} message The message to log
* @param {string} level The log severity, one of [debug, info, warning, error, critical]
* @param {boolean} broadcast
*/
export function log(message, level, broadcast) {
    let formattedMessage = "[" + level.toUpperCase() + "] " + message;
    console.log(formattedMessage);
    if (level !== "debug") {
        for (const callback of this.callbacks) {
            callback(message, level);
        }
    }
    if (broadcast) {
        for (const callback of this.broadcastCallbacks) {
            callback(message, level);
        }
    }
}
