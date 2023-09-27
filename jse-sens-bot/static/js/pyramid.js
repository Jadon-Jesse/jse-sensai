var Example = Example || {};

Example.pyramid = function() {
    // context for MatterTools.Demo
    return {
        stuff: "hello",
        apiFetch: async function fetchFromAPI(endpoint, key) {
            try {
                const res = await axios.get(endpoint, {
                  headers: {
                    Authorization: `Bearer ${key}`,
                  },
                });
                return res;
            } 
            catch (e) {
                if (axios.isAxiosError(e)) {
                  console.error(e.response?.data);
                }
                throw e;
            }
        },
        apiPost: async function _streamCompletion(payload, apiKey, onCompletion, onError) {
            try {
                const response = await axios.post('https://api.openai.com/v1/chat/completions', payload, {
                    headers: {
                      'Content-Type': 'application/json',
                      'Authorization': `Bearer ${apiKey}`
                    }
                });
                
                return onCompletion?.(response);
            } catch (error) {
                const { response } = error;

                onError?.(response, response?.data);
            }
        },
    };
};

Example.pyramid.title = 'Pyramid';
Example.pyramid.for = '>=0.14.2';

if (typeof module !== 'undefined') {
    module.exports = Example.pyramid;
}