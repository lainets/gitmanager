function scrollToBottomOf(element) {
    const rect = element.getBoundingClientRect();
    window.scroll(0, window.scrollY + rect.bottom - window.innerHeight);
}

const buttons = document.querySelectorAll("button.scroll-button");
buttons.forEach((b) => b.onclick = (event) => {
    const log_element = event.target.parentElement.parentElement.nextElementSibling;
    scrollToBottomOf(log_element);
});