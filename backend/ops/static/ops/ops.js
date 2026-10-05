// HTMX skips the swap when a request fails, so a dead backend would leave old numbers on
// screen looking current. Say so, and clear the warning on the next successful swap.
(function () {
  const banner = document.getElementById('offline')
  const show = (message) => {
    banner.textContent = message
    banner.hidden = false
  }
  document.body.addEventListener('htmx:sendError', () =>
    show('Backend unreachable: the panel shows the last data it received and keeps retrying.'),
  )
  document.body.addEventListener('htmx:responseError', (event) => {
    const xhr = event.detail.xhr
    show(`Request failed (${xhr.status}): ${xhr.responseText.slice(0, 200)}`)
  })
  document.body.addEventListener('htmx:afterSwap', () => {
    banner.hidden = true
  })
})()
