package autotest.common.ui;

import autotest.common.JsonRpcProxy;
import autotest.common.Utils;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.KeyboardListener;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.Widget;

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
        resetPage();
        
        RootPanel.get(getFetchControlsElementId()).add(idInput);
        RootPanel.get(getFetchControlsElementId()).add(idFetchButton);
        
        idInput.addKeyboardListener(new KeyboardListener() {
            public void onKeyPress(Widget sender, char keyCode, int modifiers) {
                if (keyCode == (char) KEY_ENTER)
                    fetchById(idInput.getText());
            }

            public void onKeyDown(Widget sender, char keyCode, int modifiers) {}
            public void onKeyUp(Widget sender, char keyCode, int modifiers) {}
        });
        idFetchButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                fetchById(idInput.getText());
            }
        });
    }

    protected void showText(String text, String elementId) {
        DOM.setInnerText(RootPanel.get(elementId).getElement(), text);
    }

    protected void showField(JSONObject object, String field, String elementId) {
        String value = Utils.jsonToString(object.get(field));
        showText(value, elementId);
    }

    public void resetPage() {
        showText(getNoObjectText(), getTitleElementId());
        RootPanel.get(getDataElementId()).setVisible(false);
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
        RootPanel.get(getDataElementId()).setVisible(true);
    }
    
    @Override
    protected Map<String, String> getHistoryArguments() {
        Map<String, String> arguments = super.getHistoryArguments();
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
