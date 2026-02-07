// Close alert buttons
document.addEventListener('DOMContentLoaded', function() {
    // Close alert functionality
    document.querySelectorAll('.close-alert').forEach(button => {
        button.addEventListener('click', function() {
            this.parentElement.style.display = 'none';
        });
    });
    
    // Auto-hide alerts after 5 seconds
    setTimeout(() => {
        document.querySelectorAll('.alert').forEach(alert => {
            alert.style.display = 'none';
        });
    }, 5000);
    
    // Tab functionality
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.addEventListener('click', function() {
            const tabId = this.getAttribute('data-tab');
            
            // Remove active class from all tabs and buttons
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Add active class to current tab and button
            this.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        });
    });
    
    // Dynamic unit selection based on item type
    const itemTypeSelect = document.querySelector('select[name="item_type"]');
    const unitSelect = document.querySelector('select[name="unit"]');
    
    if (itemTypeSelect && unitSelect) {
        itemTypeSelect.addEventListener('change', function() {
            const itemType = this.value;
            unitSelect.innerHTML = '<option value="">Select Unit</option>';
            
            if (itemType === 'raw_material') {
                unitSelect.innerHTML += `
                    <option value="KG">Kilogram (KG)</option>
                    <option value="LTR">Liter (LTR)</option>
                `;
            } else if (itemType === 'packing_material') {
                unitSelect.innerHTML += `
                    <option value="PCS">Pieces (PCS)</option>
                `;
            } else if (itemType === 'finished_goods') {
                unitSelect.innerHTML += `
                    <option value="PCS">Pieces (PCS)</option>
                    <option value="CARTON">Carton (CARTON)</option>
                `;
            }
        });
    }
});
