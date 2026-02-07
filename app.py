from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config.from_object('config.Config')
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'admin', 'factory', 'depot'
    depot_location = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_type = db.Column(db.String(50), nullable=False)  # 'raw_material', 'packing_material', 'finished_goods'
    item_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0)
    unit = db.Column(db.String(20), nullable=False)  # 'KG', 'LTR', 'PCS', 'CARTON'
    location = db.Column(db.String(50), nullable=False)  # 'factory' or depot name
    min_stock_level = db.Column(db.Float, default=0)
    max_stock_level = db.Column(db.Float, default=1000)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.String(80))
    
    def to_dict(self):
        return {
            'id': self.id,
            'item_type': self.item_type,
            'item_name': self.item_name,
            'quantity': self.quantity,
            'unit': self.unit,
            'location': self.location,
            'min_stock_level': self.min_stock_level,
            'max_stock_level': self.max_stock_level,
            'last_updated': self.last_updated.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_by': self.updated_by
        }

class ProductionConversion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    product_name = db.Column(db.String(200), nullable=False)
    raw_material_used = db.Column(db.Text)  # JSON string of materials used
    packing_material_used = db.Column(db.Text)  # JSON string of materials used
    quantity_produced = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), default='PCS')
    created_by = db.Column(db.String(80))
    
class TransactionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.Column(db.String(80))
    action = db.Column(db.String(100))
    location = db.Column(db.String(50))
    details = db.Column(db.Text)
    
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    # Get inventory for user's location
    if current_user.role == 'factory':
        location = 'factory'
    else:
        location = current_user.depot_location
    
    inventory_items = InventoryItem.query.filter_by(location=location).all()
    
    return render_template('dashboard.html', 
                         location=location,
                         inventory_items=inventory_items,
                         user=current_user)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied!', 'error')
        return redirect(url_for('dashboard'))
    
    # Get all inventory summary
    all_inventory = {}
    locations = ['factory', 'Dhaka', 'Chittagong', 'Jhenaidah', 'Bogra', 'Rangpur']
    
    for location in locations:
        items = InventoryItem.query.filter_by(location=location).all()
        all_inventory[location] = {
            'raw_material': sum(item.quantity for item in items if item.item_type == 'raw_material'),
            'packing_material': sum(item.quantity for item in items if item.item_type == 'packing_material'),
            'finished_goods': sum(item.quantity for item in items if item.item_type == 'finished_goods'),
            'items': items
        }
    
    return render_template('admin_dashboard.html', 
                         inventory_summary=all_inventory,
                         locations=locations)

@app.route('/inventory/add', methods=['POST'])
@login_required
def add_inventory():
    try:
        item_type = request.form.get('item_type')
        item_name = request.form.get('item_name')
        quantity = float(request.form.get('quantity', 0))
        unit = request.form.get('unit')
        
        if current_user.role == 'factory':
            location = 'factory'
        elif current_user.role == 'depot':
            location = current_user.depot_location
        else:
            location = request.form.get('location', 'factory')
        
        # Check if item exists
        existing_item = InventoryItem.query.filter_by(
            item_type=item_type,
            item_name=item_name,
            location=location,
            unit=unit
        ).first()
        
        if existing_item:
            existing_item.quantity += quantity
            existing_item.updated_by = current_user.username
            flash(f'Updated {item_name} quantity by {quantity} {unit}', 'success')
        else:
            new_item = InventoryItem(
                item_type=item_type,
                item_name=item_name,
                quantity=quantity,
                unit=unit,
                location=location,
                updated_by=current_user.username
            )
            db.session.add(new_item)
            flash(f'Added new item: {item_name} ({quantity} {unit})', 'success')
        
        # Log transaction
        log = TransactionLog(
            user=current_user.username,
            action='ADD_INVENTORY',
            location=location,
            details=f"Added {quantity} {unit} of {item_name} ({item_type})"
        )
        db.session.add(log)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/inventory/update/<int:item_id>', methods=['POST'])
@login_required
def update_inventory(item_id):
    try:
        item = InventoryItem.query.get_or_404(item_id)
        
        # Check permission
        if current_user.role == 'depot' and item.location != current_user.depot_location:
            return jsonify({'success': False, 'error': 'Permission denied'})
        
        action = request.form.get('action')
        quantity = float(request.form.get('quantity', 0))
        
        old_quantity = item.quantity
        
        if action == 'add':
            item.quantity += quantity
            action_text = f"Added {quantity}"
        elif action == 'subtract':
            if item.quantity >= quantity:
                item.quantity -= quantity
                action_text = f"Subtracted {quantity}"
            else:
                return jsonify({'success': False, 'error': 'Insufficient quantity'})
        elif action == 'set':
            item.quantity = quantity
            action_text = f"Set to {quantity}"
        else:
            return jsonify({'success': False, 'error': 'Invalid action'})
        
        item.updated_by = current_user.username
        item.last_updated = datetime.utcnow()
        
        # Log transaction
        log = TransactionLog(
            user=current_user.username,
            action='UPDATE_INVENTORY',
            location=item.location,
            details=f"{action_text} {item.unit} of {item.item_name}. Old: {old_quantity}, New: {item.quantity}"
        )
        db.session.add(log)
        
        db.session.commit()
        return jsonify({'success': True, 'new_quantity': item.quantity})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/factory/conversion', methods=['GET', 'POST'])
@login_required
def factory_conversion():
    if current_user.role not in ['factory', 'admin']:
        flash('Access denied! Only factory users can access this page.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        try:
            product_name = request.form.get('product_name')
            quantity_produced = float(request.form.get('quantity_produced', 0))
            
            # Get raw materials used (from form data)
            raw_materials = []
            for i in range(int(request.form.get('raw_material_count', 0))):
                material_id = request.form.get(f'raw_material_id_{i}')
                material_qty = float(request.form.get(f'raw_material_qty_{i}', 0))
                raw_materials.append({'id': material_id, 'quantity_used': material_qty})
            
            # Get packing materials used
            packing_materials = []
            for i in range(int(request.form.get('packing_material_count', 0))):
                material_id = request.form.get(f'packing_material_id_{i}')
                material_qty = float(request.form.get(f'packing_material_qty_{i}', 0))
                packing_materials.append({'id': material_id, 'quantity_used': material_qty})
            
            # Update raw materials inventory
            for material in raw_materials:
                item = InventoryItem.query.get(material['id'])
                if item:
                    item.quantity -= material['quantity_used']
                    if item.quantity < 0:
                        item.quantity = 0
            
            # Update packing materials inventory
            for material in packing_materials:
                item = InventoryItem.query.get(material['id'])
                if item:
                    item.quantity -= material['quantity_used']
                    if item.quantity < 0:
                        item.quantity = 0
            
            # Add finished goods
            finished_good = InventoryItem.query.filter_by(
                item_type='finished_goods',
                item_name=product_name,
                location='factory',
                unit='PCS'
            ).first()
            
            if finished_good:
                finished_good.quantity += quantity_produced
            else:
                finished_good = InventoryItem(
                    item_type='finished_goods',
                    item_name=product_name,
                    quantity=quantity_produced,
                    unit='PCS',
                    location='factory',
                    updated_by=current_user.username
                )
                db.session.add(finished_good)
            
            # Record production conversion
            conversion = ProductionConversion(
                product_name=product_name,
                raw_material_used=str(raw_materials),
                packing_material_used=str(packing_materials),
                quantity_produced=quantity_produced,
                unit='PCS',
                created_by=current_user.username
            )
            db.session.add(conversion)
            
            # Log transaction
            log = TransactionLog(
                user=current_user.username,
                action='PRODUCTION_CONVERSION',
                location='factory',
                details=f"Produced {quantity_produced} PCS of {product_name}"
            )
            db.session.add(log)
            
            db.session.commit()
            flash('Production conversion completed successfully!', 'success')
            return redirect(url_for('factory_conversion'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
    
    # Get raw and packing materials for factory
    raw_materials = InventoryItem.query.filter_by(
        location='factory',
        item_type='raw_material'
    ).all()
    
    packing_materials = InventoryItem.query.filter_by(
        location='factory',
        item_type='packing_material'
    ).all()
    
    return render_template('factory_conversion.html',
                         raw_materials=raw_materials,
                         packing_materials=packing_materials)

@app.route('/api/inventory/<location>')
@login_required
def get_inventory_by_location(location):
    # Check permissions
    if current_user.role == 'depot' and location != current_user.depot_location:
        return jsonify({'error': 'Permission denied'}), 403
    
    if current_user.role == 'factory' and location != 'factory':
        return jsonify({'error': 'Permission denied'}), 403
    
    items = InventoryItem.query.filter_by(location=location).all()
    return jsonify([item.to_dict() for item in items])

@app.route('/api/locations')
@login_required
def get_locations():
    if current_user.role == 'admin':
        locations = ['factory', 'Dhaka', 'Chittagong', 'Jhenaidah', 'Bogra', 'Rangpur']
    elif current_user.role == 'factory':
        locations = ['factory']
    else:
        locations = [current_user.depot_location]
    
    return jsonify(locations)

@app.route('/api/depot/transfer', methods=['POST'])
@login_required
def transfer_to_depot():
    try:
        item_id = request.form.get('item_id')
        quantity = float(request.form.get('quantity', 0))
        to_location = request.form.get('to_location')
        
        if current_user.role not in ['factory', 'admin']:
            return jsonify({'success': False, 'error': 'Permission denied'})
        
        source_item = InventoryItem.query.get_or_404(item_id)
        
        if source_item.location != 'factory':
            return jsonify({'success': False, 'error': 'Can only transfer from factory'})
        
        if source_item.quantity < quantity:
            return jsonify({'success': False, 'error': 'Insufficient quantity'})
        
        # Reduce quantity at factory
        source_item.quantity -= quantity
        
        # Find or create item at depot
        depot_item = InventoryItem.query.filter_by(
            item_type=source_item.item_type,
            item_name=source_item.item_name,
            unit=source_item.unit,
            location=to_location
        ).first()
        
        if depot_item:
            depot_item.quantity += quantity
            depot_item.updated_by = current_user.username
        else:
            depot_item = InventoryItem(
                item_type=source_item.item_type,
                item_name=source_item.item_name,
                quantity=quantity,
                unit=source_item.unit,
                location=to_location,
                updated_by=current_user.username
            )
            db.session.add(depot_item)
        
        # Log transaction
        log = TransactionLog(
            user=current_user.username,
            action='TRANSFER_TO_DEPOT',
            location=to_location,
            details=f"Transferred {quantity} {source_item.unit} of {source_item.item_name} from factory to {to_location}"
        )
        db.session.add(log)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# Initialize database and create admin user
@app.before_first_request
def create_tables_and_admin():
    db.create_all()
    
    # Create admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            role='admin'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        
        # Create factory user
        factory_user = User(
            username='factory',
            role='factory'
        )
        factory_user.set_password('factory123')
        db.session.add(factory_user)
        
        # Create depot users
        depots = ['Dhaka', 'Chittagong', 'Jhenaidah', 'Bogra', 'Rangpur']
        for depot in depots:
            user = User(
                username=depot.lower(),
                role='depot',
                depot_location=depot
            )
            user.set_password(f'{depot.lower()}123')
            db.session.add(user)
        
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
