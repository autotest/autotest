package autotest.common;

import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.Timer;
import com.google.gwt.user.client.ui.RootPanel;

public class CommonClassFactory {

    public static void globalInitialize() {
        setupMOTD();

        Timer timer = new Timer() {
            @Override
            public void run() {
                refreshMOTD();
            }
        };

        // schedule every 10 minutes
        timer.scheduleRepeating(10 * 60 * 1000);
    }

    public static void setupMOTD() {
        String motd = StaticDataRepository.getRepository().getData(
                "motd").isString().stringValue();
        RootPanel.get("motd").getElement().setInnerHTML(motd);
    }

    public static void refreshMOTD() {
        JsonRpcProxy.getProxy().rpcCall("get_motd", null, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                String motd = result.isString().stringValue();
                RootPanel.get("motd").getElement().setInnerHTML(motd);
            }
        });
    }
}
