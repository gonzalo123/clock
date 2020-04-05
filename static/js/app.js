let getWsUri = () => {
  return window.location.protocol === "https:" ? "wss" : "ws" +
    '://' + window.location.host +
    "/time/tic/"
}

let render = value => {
  document.querySelector('#display').innerHTML = value
}

let ws = new ReconnectingWebSocket(getWsUri())

ws.onmessage = e => {
  const data = JSON.parse(e.data);
  render(data.message.time)
}

ws.onopen = async () => {
  let response = await axios.get("/api/initial_state")
  render(response.data.current)
}
