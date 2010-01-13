package autotest.tko;

import autotest.common.SimpleCallback;
import autotest.common.ui.NotifyManager;
import autotest.common.ui.SimplifiedList;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.user.client.ui.HasText;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class ParameterizedFieldListPresenter implements ClickHandler {
    public interface Display {
        public interface FieldWidget {
            public HasClickHandlers getDeleteLink();
        }

        public SimplifiedList getTypeSelect();
        public HasText getValueInput();
        public HasClickHandlers getAddLink();
        public FieldWidget addFieldWidget(String name, String filteringName); 
        public void removeFieldWidget(FieldWidget widget);
    }
    
    private Display display;
    private HeaderFieldCollection headerFields;
    private Map<ParameterizedField, Display.FieldWidget> fieldInputMap = 
        new HashMap<ParameterizedField, Display.FieldWidget>();
    private Set<Object> fieldIds = new HashSet<Object>();
    private SimpleCallback changeListener;

    /**
     * @param headerFields Generated ParameterizedFields will be added to this (and removed when
     * they're deleted) 
     */
    public ParameterizedFieldListPresenter(HeaderFieldCollection headerFields) {
        this.headerFields = headerFields;
    }

    public void bindDisplay(Display display) {
        this.display = display;
        display.getAddLink().addClickHandler(this);
        populateTypeSelect();
    }

    public void setListener(SimpleCallback changeListener) {
        this.changeListener = changeListener;
    }

    private void populateTypeSelect() {
        for (String name : ParameterizedField.getFieldTypeNames()) {
            display.getTypeSelect().addItem(name, name);
        }
    }

    @Override
    public void onClick(ClickEvent event) {
        assert event.getSource() == display.getAddLink();

        String type = display.getTypeSelect().getSelectedName();
        String value = display.getValueInput().getText();
        if (value.isEmpty()) {
            NotifyManager.getInstance().showError("You must provide a value");
            return;
        }
        
        ParameterizedField field = createField(type, value);
        if (fieldIds.contains(field.getIdentifier())) {
            NotifyManager.getInstance().showError("This field already exists: " + field.getName());
            return;
        }

        addField(field);
        changeListener.doCallback(this);
        display.getValueInput().setText("");
    }
    
    private ParameterizedField createField(String type, String value) {
        return ParameterizedField.newInstance(type, value);
    }

    private void addField(final ParameterizedField field) {
        headerFields.add(field);

        Display.FieldWidget fieldWidget = display.addFieldWidget(field.getName(), 
                                                                 field.getFilteringName());
        fieldInputMap.put(field, fieldWidget);
        fieldWidget.getDeleteLink().addClickHandler(new ClickHandler() {
            @Override
            public void onClick(ClickEvent event) {
                deleteField(field);
                changeListener.doCallback(this);
            }
        });

        fieldIds.add(field.getIdentifier());
    }

    public void addFieldIfNotPresent(String type, String name) {
        ParameterizedField field = createField(type, name);
        if (!fieldIds.contains(field.getIdentifier())) {
            addField(field);
        }
    }

    private void deleteField(ParameterizedField field) {
        headerFields.remove(field);
        Display.FieldWidget widget = fieldInputMap.remove(field);
        display.removeFieldWidget(widget);
        fieldIds.remove(field.getIdentifier());
    }

    private String getListKey(int index) {
        return "parameterized_field_" + Integer.toString(index);
    }

    public void addHistoryArguments(Map<String, String> arguments) {
        int index = 0;
        for (ParameterizedField field : fieldInputMap.keySet()) {
            String baseKey = getListKey(index);
            arguments.put(baseKey + "_type", field.getTypeName());
            arguments.put(baseKey + "_value", field.getValue());
            index++;
        }
    }

    public void handleHistoryArguments(Map<String, String> arguments) {
        reset();
        for (int index = 0; ; index++) {
            String baseKey = getListKey(index);
            String typeKey = baseKey + "_type";
            String valueKey = baseKey + "_value";
            if (!arguments.containsKey(typeKey) || !arguments.containsKey(valueKey)) {
                break;
            }

            String typeName = arguments.get(typeKey), value = arguments.get(valueKey);
            addField(createField(typeName, value));
        }
        changeListener.doCallback(this);
    }

    private void reset() {
        // avoid ConcurrentModificationException
        List<ParameterizedField> fieldListCopy =
            new ArrayList<ParameterizedField>(fieldInputMap.keySet());
        for (ParameterizedField field : fieldListCopy) {
            deleteField(field);
        }
    }
}
