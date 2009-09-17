package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.ui.ExtendedListBox;

import com.google.gwt.event.dom.client.ChangeEvent;
import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Composite;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;

public class PreconfigSelector extends Composite {
    public static final String NO_PRECONFIG = "----------";
    
    public static interface PreconfigHandler {
        public void handlePreconfig(Map<String, String> preconfigParameters);
    }

    private ExtendedListBox selector = new ExtendedListBox();
    private JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    private String preconfigType;
    private PreconfigHandler listener;

    public PreconfigSelector(final String preconfigType, final PreconfigHandler listener) {
        this.preconfigType = preconfigType;
        this.listener = listener;
        
        initializePreconfigList(preconfigType);
        
        selector.addChangeHandler(new ChangeHandler() {
            public void onChange(ChangeEvent event) {
                loadSelectedPreconfig();
            }
        });
        
        initWidget(selector);
    }

    private void initializePreconfigList(final String preconfigType) {
        selector.addItem(NO_PRECONFIG);
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONObject preconfigs = staticData.getData("preconfigs").isObject();
        Set<String> keys = preconfigs.get(preconfigType).isObject().keySet();
        for (String key : keys) {
            selector.addItem(key);
        }
    }

    private void loadSelectedPreconfig() {
        String name = selector.getSelectedValue();
        if (name.equals(NO_PRECONFIG)) {
            return;
        }
        selector.setSelectedIndex(0);
        
        JSONObject params = new JSONObject();
        params.put("name", new JSONString(name));
        params.put("type", new JSONString(preconfigType));
        rpcProxy.rpcCall("get_preconfig", params, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                JSONObject config = result.isObject();
                Map<String, String> map = new HashMap<String, String>();
                for (String key : config.keySet()) {
                    map.put(key, Utils.jsonToString(config.get(key)));
                }
                listener.handlePreconfig(map);
            }
        });
    }
}
