package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.ChangeListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Widget;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;

public class PreconfigSelector extends Composite {
    
    public static final String NO_PRECONFIG = "----------";
    
    private ListBox selector = new ListBox();
    private JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    
    public PreconfigSelector(final String preconfigType, final GraphingFrontend parent) {
        selector.addItem(NO_PRECONFIG);
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONObject preconfigs = staticData.getData("preconfigs").isObject();
        Set<String> keys = preconfigs.get(preconfigType).isObject().keySet();
        for (String key : keys) {
            selector.addItem(key);
        }
        
        selector.addChangeListener(new ChangeListener() {
            public void onChange(Widget sender) {
                String name = selector.getValue(selector.getSelectedIndex());
                
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
                        parent.handleHistoryArguments(map);
                    }
                });
            }
        });
        
        initWidget(selector);
    }
}
