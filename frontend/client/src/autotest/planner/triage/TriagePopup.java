package autotest.planner.triage;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.ui.SimplifiedList;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.event.logical.shared.CloseEvent;
import com.google.gwt.event.logical.shared.CloseHandler;
import com.google.gwt.event.logical.shared.HasCloseHandlers;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONBoolean;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.HasValue;
import com.google.gwt.user.client.ui.PopupPanel;

import java.util.List;

public class TriagePopup implements ClickHandler, CloseHandler<PopupPanel> {
    public static interface Display extends HasCloseHandlers<PopupPanel> {
        public HasClickHandlers getCloseButton();
        public HasText getLabelsField();
        public HasText getKeyvalsField();
        public HasText getBugsField();
        public HasText getReasonField();
        public SimplifiedList getHostActionField();
        public SimplifiedList getTestActionField();
        public HasValue<Boolean> getInvalidateField();
        public HasClickHandlers getApplyButton();
        public void center();
        public void hide();
    }
    
    public static interface Listener {
        public void onTriage();
    }
    
    private Display display;
    private Listener listener;
    private List<Integer> ids;
    private boolean triaged = false;
    
    public TriagePopup(Listener listener, List<Integer> ids) {
        this.listener = listener;
        this.ids = ids;
    }
    
    public void bindDisplay(Display display) {
        this.display = display;
        display.addCloseHandler(this);
        populateActionsFields();
        setHandlers();
    }
    
    public void render() {
        display.center();
    }
    
    public List<Integer> getIds() {
        return ids;
    }
    
    private void populateActionsFields() {
        populateList("host_actions", display.getHostActionField());
        populateList("test_actions", display.getTestActionField());
    }
    
    private void populateList(String staticDataKey, SimplifiedList list) {
        JSONArray choices = StaticDataRepository.getRepository().getData(staticDataKey).isArray();
        for (int i = 0; i < choices.size(); i++) {
            String item = choices.get(i).isString().stringValue();
            list.addItem(item, item);
        }
    }
    
    private void setHandlers() {
        display.getCloseButton().addClickHandler(this);
        display.getApplyButton().addClickHandler(this);
    }
    
    @Override
    public void onClick(ClickEvent event) {
        if (event.getSource() == display.getCloseButton()) {
            display.hide();
        } else {
            assert event.getSource() == display.getApplyButton();
            JsonRpcProxy proxy = JsonRpcProxy.getProxy();
            
            JSONObject params = getParams();
            
            proxy.rpcCall("process_failures", params, new JsonRpcCallback() {
                @Override
                public void onSuccess(JSONValue result) {
                    triaged = true;
                    display.hide();
                }
            });
        }
    }
    
    private JSONObject getParams() {
        JSONObject params = new JSONObject();
        params.put("failure_ids", Utils.integersToJSON(ids));
        params.put("host_action", new JSONString(display.getHostActionField().getSelectedName()));
        params.put("test_action", new JSONString(display.getTestActionField().getSelectedName()));
        
        if (!display.getLabelsField().getText().trim().equals("")) {
            params.put("labels", parseCommaDelimited(display.getLabelsField().getText()));
        }
        
        if (!display.getKeyvalsField().getText().trim().equals("")) {
            JSONObject keyvals = new JSONObject();
            for (String keyval : display.getKeyvalsField().getText().split("\n")) {
                String split[] = keyval.split("=", 2);
                keyvals.put(split[0].trim(), new JSONString(split[1].trim()));
            }
            params.put("keyvals", keyvals);
        }
        
        if (!display.getBugsField().getText().trim().equals("")) {
            params.put("bugs", parseCommaDelimited(display.getBugsField().getText()));
        }
        
        if (!display.getReasonField().getText().trim().equals("")) {
            params.put("reason", new JSONString(display.getReasonField().getText()));
        }
        
        params.put("invalidate", JSONBoolean.getInstance(display.getInvalidateField().getValue()));
        
        return params;
    }
    
    private JSONArray parseCommaDelimited(String line) {
        JSONArray values = new JSONArray();
        for (String value : line.split(",")) {
            values.set(values.size(), new JSONString(value.trim()));
        }
        return values;
    }

    @Override
    public void onClose(CloseEvent<PopupPanel> event) {
        if (triaged) {
            listener.onTriage();
        }
    }
}
