// Nested preview dialogs share the same scroll lock and can close in either order.
let locks = 0,
  previous = ''
export function lockBodyScroll() {
  if (locks === 0) {
    previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
  }
  locks += 1
  let released = false
  return () => {
    if (released) return
    released = true
    locks -= 1
    if (locks === 0) document.body.style.overflow = previous
  }
}
