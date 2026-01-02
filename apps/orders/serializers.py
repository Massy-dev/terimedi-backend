from rest_framework import serializers
from .models import Commande, OrderItem
from apps.pharmacies.models import Pharmacy
from .utils import calculer_distance
import json

class OrderItemSerializer(serializers.ModelSerializer):
    #prescription_image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ["id", "produit", "quantity", "unit_price", "subtotal", "prescription_image",'disponibilite', 'note_pharmacie',]
        read_only_fields = ["id","subtotal"]
        
    def get_image_url(self, obj):
        
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

class CommandeSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    client_nom = serializers.SerializerMethodField()
    #pharmacie_nom = serializers.SerializerMethodField()
    #produits = OrderItemSerializer(many=True, read_only=True)
    

    class Meta:
        model = Commande
        fields = [
            "id",
            "order_number",
            'client_nom',
            #'pharmacie_nom',
            "clt_phone",
            "patient_latitude",
            "patient_longitude",
            "statut",
            "total_amount",
            "date_commande",
            "items",   # utilisé pour l'envoi
            #"produits" # pour le retour
        ]
        read_only_fields = [
            "id",
            "order_number",
            "statut",
            "total_amount",
            "date_commande"
            'client_nom',
            #'pharmacie_nom',
        ]

    def get_client_nom(self, obj):
        return f"{obj.client.phone} {obj.client.username}"

    def get_pharmacie_nom(self, obj):
        return obj.pharmacie.name if obj.pharmacie else None

    def validate(self, attrs):
        required_fields = ['patient_latitude', 'patient_longitude']
        missing_fields = [f for f in required_fields if not attrs.get(f)]
        if missing_fields:
            raise serializers.ValidationError({field: "Ce champ est obligatoire." for field in missing_fields})
        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        latitude = validated_data.get("patient_latitude")
        longitude = validated_data.get("patient_longitude")

        pharmacies = Pharmacy.objects.filter(is_open=True, is_approved=True)
        if not pharmacies.exists():
            raise serializers.ValidationError("Aucune pharmacie disponible actuellement.")

        # Trouver la pharmacie la plus proche
        pharmacie_proche = min(
            pharmacies,
            key=lambda p: calculer_distance(latitude, longitude, p.latitude, p.longitude)
        )

        # Créer la commande
        user = self.context["request"].user
        print("User du serialiser order----------------", user)
        commande = Commande.objects.create(
            client=user,
            pharmacie=pharmacie_proche,
            **validated_data
        )

        # Créer les items associés
        for item_data in items_data:
            OrderItem.objects.create(order=commande, **item_data)

        commande.update_total()
        return commande


class MedicamentsField(serializers.Field):
    """Champ personnalisé pour gérer les médicaments (JSON string ou liste)"""
    
    def to_internal_value(self, data):
        """Convertit les données en liste de dictionnaires"""
        import re
        
        print(f"DEBUG MedicamentsField.to_internal_value - data type: {type(data)}, data: {data}")
        
        # Si data est vide ou None
        if data is None or data == serializers.empty:
            raise serializers.ValidationError("Le champ medicaments est requis")
        
        # Si c'est déjà une liste
        if isinstance(data, list):
            # Si la liste est vide
            if len(data) == 0:
                raise serializers.ValidationError("Au moins un médicament est requis")
            
            # Si la liste contient une string (JSON), la parser
            if len(data) == 1 and isinstance(data[0], str):
                print(f"DEBUG MedicamentsField - list contains string, parsing: {data[0][:100]}")
                data = data[0]
            else:
                # Vérifier que tous les éléments sont des dicts
                result = []
                for item in data:
                    if isinstance(item, dict):
                        result.append(item)
                    elif isinstance(item, list):
                        # Si imbriqué, aplatir
                        result.extend([i for i in item if isinstance(i, dict)])
                if result:
                    print(f"DEBUG MedicamentsField - returning list of dicts: {result}")
                    return result
                # Si aucun dict trouvé, essayer de parser le premier élément comme string
                if len(data) > 0 and isinstance(data[0], str):
                    data = data[0]
        
        # Si c'est une string, la parser
        if isinstance(data, str):
            data = data.strip()
            print(f"DEBUG MedicamentsField - parsing string: {data[:100]}")
            
            # Essayer de parser comme JSON valide
            try:
                parsed = json.loads(data)
                if isinstance(parsed, list):
                    print(f"DEBUG MedicamentsField - parsed JSON successfully: {parsed}")
                    return parsed
            except json.JSONDecodeError as e:
                print(f"DEBUG MedicamentsField - JSON decode failed: {e}")
            
            # Parser le format Dart/JavaScript: [{produit: fre, quantity: 45}]
            try:
                medicaments_list = []
                objects = re.findall(r'\{([^}]+)\}', data)
                for obj_str in objects:
                    med_dict = {}
                    pairs = re.findall(r'(\w+):\s*([^,}]+)', obj_str)
                    for key, value in pairs:
                        value = value.strip()
                        if value.isdigit():
                            med_dict[key] = int(value)
                        elif re.match(r'^-?\d+\.\d+$', value):
                            med_dict[key] = float(value)
                        else:
                            med_dict[key] = value
                    medicaments_list.append(med_dict)
                
                if medicaments_list:
                    print(f"DEBUG MedicamentsField - parsed manually: {medicaments_list}")
                    return medicaments_list
            except Exception as e:
                print(f"DEBUG MedicamentsField parsing error: {e}")
        
        raise serializers.ValidationError(
            f"Format invalide pour medicaments. Attendu: liste de dictionnaires ou JSON string. Reçu: {type(data).__name__}, valeur: {str(data)[:100]}"
        )
    
    def to_representation(self, value):
        """Convertit la liste en représentation"""
        return value if isinstance(value, list) else []

class DevisSerializer(serializers.Serializer):
    """Serializer pour la création du devis par la pharmacie"""
    items = serializers.ListField(
        child=serializers.DictField()
    )
    delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2)

    

    def validate_medicaments(self, value):
        print("DEBUG DevisSerializer - delivery_fee:", value)
        """Valider que tous les médicaments ont un prix et une disponibilité"""
        
        for med in value:
            if 'id' not in med:
                raise serializers.ValidationError("ID du médicament requis")
            if 'unit_price' not in med:
                raise serializers.ValidationError("Prix unitaire requis")
            if 'disponibilite' not in med:
                raise serializers.ValidationError("Disponibilité requise")
        return value

class RefusCommandeSerializer(serializers.Serializer):
    """Serializer pour le refus de commande par le client"""
    raison_refus = serializers.CharField(required=False, allow_blank=True)
    demander_revision = serializers.BooleanField(default=False)


class CommandeCreateSerializer(serializers.Serializer):
    """Serializer pour la création de commande avec upload d'images"""
    client = serializers.HiddenField(default=serializers.CurrentUserDefault())
    patient_latitude = serializers.CharField(max_length=50)  # Augmenté pour gérer les coordonnées GPS
    patient_longitude = serializers.CharField(max_length=50)  # Augmenté pour gérer les coordonnées GPS
    #notes = serializers.CharField(required=False, allow_blank=True)
    clt_phone = serializers.CharField(max_length=10)
    statut = serializers.CharField(max_length=20, default='en_attente')
    medicaments = MedicamentsField()


    def validate_medicaments(self, value):
        """Valider la structure des médicaments"""
        if not isinstance(value, list):
            raise serializers.ValidationError("medicaments doit être une liste")
        
        if len(value) == 0:
            raise serializers.ValidationError("Au moins un médicament est requis")
        
        for med in value:
            if not isinstance(med, dict):
                raise serializers.ValidationError(
                    f"Chaque médicament doit être un dictionnaire, reçu: {type(med).__name__}"
                )
            if 'produit' not in med or 'quantity' not in med:
                raise serializers.ValidationError(
                    "Chaque médicament doit avoir 'produit' et 'quantity'"
                )
            # Convertir quantity en int si c'est une string
            if isinstance(med['quantity'], str):
                try:
                    med['quantity'] = int(med['quantity'])
                except ValueError:
                    raise serializers.ValidationError(
                        "La quantité doit être un nombre entier"
                    )
            if not isinstance(med['quantity'], int) or med['quantity'] <= 0:
                raise serializers.ValidationError(
                    "La quantité doit être un entier positif"
                )
        return value