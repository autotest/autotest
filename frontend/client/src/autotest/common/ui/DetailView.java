package autotest.common.ui;

import autotest.common.JsonRpcProxy;
import autotest.common.Utils;
import autotest.common.CustomHistory.HistoryToken;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.KeyCodes;
import com.google.gwt.event.dom.client.KeyPressEvent;
import com.google.gwt.event.dom.client.KeyPressHandler;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.TextBox;

import java.util.Map;



public abstract class DetailView extends TabView {
    protected static final String NO_OBJECT = "";
    
    protected JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    protected TextBox idInput = new TextBox();
    protected Button idFetchButton = new Button("Go");
    
    protected abstract String getNoObjectText();
    protected abstract String getFetchControlsElementId();
    protected abstract String getDataElementId();    
    protected abstract String getTitleElementId();
    protected abstract String getObjectId();
    protected abstract void setObjectId(String id); // throws IllegalArgumentException
    protected abstract void fetchData();
    
    @Override
    public void initialize() {
        super.initialize();
        resetPage();
        
        addWidget(idInput, getFetchControlsElementId());
        addWidget(idFetchButton, getFetchControlsElementId());
        
        idInput.addKeyPressHandler(new KeyPressHandler() {
            public void onKeyPress (KeyPressEvent event) {
                if (event.getCharCode() == (char) KeyCodes.KEY_ENTER)
                    fetchById(idInput.getText());
            }
        });
        idFetchButton.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                fetchById(idInput.getText());
            }
        });
    }

    protected void showText(String text, String elementId) {
        getElementById(elementId).setInnerText(text);
    }

    protected void showField(JSONObject object, String field, String elementId) {
        String value = Utils.jsonToString(object.get(field));
        showText(value, elementId);
    }

    public void resetPage() {
        showText(getNoObjectText(), getTitleElementId());
        Utils.setElementVisible(getDataElementId(), false);
    }
    
    public void updateObjectId(String id) {
        try {
            setObjectId(id);
        }
        catch (IllegalArgumentException exc) {
            String error = "Invalid input: " + id;
            NotifyManager.getInstance().showError(error);
            return;
        }
        idInput.setText(id);
    }
    
    public void fetchById(String id) {
        updateObjectId(id);
        updateHistory();
        refresh();
    }
    
    @Override
    public void refresh() {
        super.refresh();
        if (!getObjectId().equals(NO_OBJECT))
            fetchData();
    }
    
    protected void displayObjectData(String title) {
        showText(title, getTitleElementId());
        Utils.setElementVisible(getDataElementId(), true);
    }
    
    @Override
    public HistoryToken getHistoryArguments() {
        HistoryToken arguments = super.getHistoryArguments();
        String objectId = getObjectId();
        if (!objectId.equals(NO_OBJECT)) {
            arguments.put("object_id", objectId);
        }
        return arguments;
    }
    
    @Override
    public void handleHistoryArguments(Map<String, String> arguments) {
        String objectId = arguments.get("object_id");
        if (objectId == null) {
            resetPage();
            return;
        }
        
        try {
            updateObjectId(objectId);
        }
        catch (IllegalArgumentException exc) {
            return;
        }
    }
}
