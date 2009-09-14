package autotest.tko;

import autotest.common.ui.MultiListSelectPresenter;
import autotest.common.ui.MultiListSelectPresenter.Item;

import com.google.gwt.user.client.ui.HasText;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

public class ParameterizedFieldListPresenter implements MultiListSelectPresenter.GeneratorHandler {
    public interface Display {
        public HasText addFieldInput(String name);
        public void removeFieldInput(HasText input);
    }

    private int nameCounter;
    private Display display;
    private Map<String, ParameterizedField> fieldMap = new HashMap<String, ParameterizedField>();
    private Map<ParameterizedField, HasText> fieldInputMap = 
        new HashMap<ParameterizedField, HasText>();

    public void bindDisplay(Display display) {
        this.display = display;
    }

    @Override
    public Item generateItem(Item generatorItem) {
        String sqlName = generatorItem.value + Integer.toString(nameCounter);
        nameCounter++;
        ParameterizedField field = addFieldBySqlName(sqlName);
        return getItemForField(field);
    }

    public ParameterizedField addFieldBySqlName(String sqlName) {
        ParameterizedField field = ParameterizedField.fromSqlName(sqlName);
        fieldMap.put(field.getSqlName(), field);

        // ensure name counter never overlaps this field name
        if (nameCounter <= field.getFieldNumber()) {
            nameCounter = field.getFieldNumber() + 1;
        }

        HasText fieldInput = display.addFieldInput(field.getName());
        fieldInputMap.put(field, fieldInput);

        return field;
    }

    public Item getItemForField(ParameterizedField field) {
        return Item.createGeneratedItem(field.getName(), field.getSqlName());
    }

    @Override
    public void onRemoveGeneratedItem(Item generatedItem) {
        // iterate over copy so we can mutate
        for (ParameterizedField field : new ArrayList<ParameterizedField>(fieldInputMap.keySet())) {
            if (field.getSqlName().equals(generatedItem.value)) {
                HasText fieldInput = fieldInputMap.remove(field);
                display.removeFieldInput(fieldInput);
                fieldMap.remove(field.getSqlName());
                return;
            }
        }
        
        throw new IllegalArgumentException("Field " + generatedItem.value + " not found");
    }

    public void updateStateFromView() {
        for (ParameterizedField field : fieldInputMap.keySet()) {
            String newValue = fieldInputMap.get(field).getText();
            field.setValue(newValue);
        }
    }

    public void updateViewFromState() {
        for (ParameterizedField field : fieldInputMap.keySet()) {
            fieldInputMap.get(field).setText(field.getValue());
        }
    }

    public Collection<ParameterizedField> getFields() {
        return Collections.unmodifiableCollection(fieldInputMap.keySet());
    }

    public boolean areAllInputsFilled() {
        for (HasText fieldInput : fieldInputMap.values()) {
            if (fieldInput.getText().isEmpty()) {
                return false;
            }
        }
        return true;
    }

    public HeaderField getField(String sqlName) {
        assert fieldMap.containsKey(sqlName);
        return fieldMap.get(sqlName);
    }
}
