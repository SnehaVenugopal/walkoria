// Category Management JavaScript

// Show toast notification
function showToast(message, type) {
  // Create toast element
  const toast = document.createElement("div")
  toast.className = `alert alert-${type}`
  toast.style.position = "fixed"
  toast.style.top = "20px"
  toast.style.right = "20px"
  toast.style.zIndex = "9999"
  toast.style.minWidth = "300px"
  toast.innerHTML = message

  // Add to document
  document.body.appendChild(toast)

  // Remove after 3 seconds
  setTimeout(() => {
    toast.style.opacity = "0"
    toast.style.transition = "opacity 0.5s ease"
    setTimeout(() => {
      document.body.removeChild(toast)
    }, 500)
  }, 3000)
}

// Handle form validation
function validateCategoryForm() {
  const categoryName = document.getElementById("categoryName").value.trim()

  if (!categoryName) {
    document.getElementById("nameError").textContent = "Category name is required"
    document.getElementById("nameError").style.display = "block"
    return false
  }

  if (!/^[a-zA-Z\s]+$/.test(categoryName)) {
    document.getElementById("nameError").textContent = "Category name can only contain letters and spaces"
    document.getElementById("nameError").style.display = "block"
    return false
  }

  return true
}

// Initialize event listeners
document.addEventListener("DOMContentLoaded", () => {
  // Add event listener for category name input
  const categoryNameInput = document.getElementById("categoryName")
  if (categoryNameInput) {
    categoryNameInput.addEventListener("input", function () {
      if (this.value.trim()) {
        document.getElementById("nameError").style.display = "none"
      }
    })
  }

  // Add event listener for category form submission
  const categoryForm = document.getElementById("categoryForm")
  if (categoryForm) {
    categoryForm.addEventListener("submit", (e) => {
      if (!validateCategoryForm()) {
        e.preventDefault()
      }
    })
  }
})
